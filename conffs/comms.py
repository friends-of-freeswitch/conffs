# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
Communication and transport for remote config file management.
"""
import logging
import os
import plumbum
import paramiko
from getpass import getpass


log = logging.getLogger('conffs')


SSH_OPTS = ['-o', 'UserKnownHostsFile=/dev/null',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'ServerAliveInterval=5']


def get_pkey(keyfile, prompt=True, password=None):
    """Get a private key references prompting for password by default.
    """
    try:
        return paramiko.RSAKey.from_private_key_file(
            keyfile, password=password)
    except paramiko.ssh_exception.PasswordRequiredException:
        if not prompt:
            raise

        return paramiko.RSAKey.from_private_key_file(
            keyfile, password=getpass("Password for {}: ".format(keyfile)))


def get_sftp(hostname, port=22, user='root', keyfile=None, password=None,
             keypw=None, pkey=None):
    """Get an SFTP connection using paramiko and plumbum.
    """
    def get_transport(**kwargs):
        transport = paramiko.Transport(hostname, port)
        transport.connect(**kwargs)
        return transport

    def get_sftp(transport):
        return paramiko.SFTPClient.from_transport(transport)

    if keyfile:
        pkey = pkey or get_pkey(keyfile, password=keypw)
        try:
            transport = get_transport(username=user, pkey=pkey)
            return get_sftp(transport)
        except paramiko.ssh_exception.AuthenticationException:
            log.warn("Failed to auth ssh with keyfile {}".format(keyfile))

    log_message = "Trying SSH connection to {} with credentials {}:{}"
    log.info(log_message.format(hostname, user, password))
    transport = get_transport(username=user, password=password)
    return get_sftp(transport)


def get_ssh(hostname, port=22, user='root', keyfile=None, password=None,
            keypw=None, pkey=None):
    """Get a ``plumbum.SshMachine`` instance.
    """
    settings = {'port': port, 'ssh_opts': SSH_OPTS, 'scp_opts': SSH_OPTS}

    if user:
        settings['user'] = user

    if keyfile:
        keyfile = os.path.expanduser(keyfile)
        assert os.path.isfile(keyfile), 'No keyfile {} exists?'.format(keyfile)
        log.info("Attempting to auth ssh with keyfile {}".format(keyfile))
        settings['keyfile'] = keyfile
    elif password:
        settings['password'] = password

    return plumbum.SshMachine(hostname, **settings)
