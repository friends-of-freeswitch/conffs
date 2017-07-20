# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
conffs: A Python ORM API for configuring and managing FreeSWITCH
        configuration using Python data structures.
"""
import logging
from .comms import get_ssh, get_sftp, get_pkey
from .manage import manage_config, cli, CLIConnectionError, CLIError


__package__ = 'conffs'
__version__ = '0.1.alpha'
__author__ = ('Sangoma Technologies', 'tgoodlet@sangoma.com')
__all__ = ['find_root', 'manage', 'manage_config']


log = logging.getLogger('conffs')


def find_root(ssh, fscli, runpath):
    '''Find and return the root configuration directory
    for the managed FreeSWITCH process.
    '''
    try:
        return ssh.path(fscli('global_getvar', 'conf_dir'))
    except CLIError:
        # older versions of fs do not support the `conf_dir` var
        # so rely on the provided runtime path.
        root = ssh.path(runpath).join('conf')
        if not root.exists():
            # a system packaged version?
            root = ssh.path('/etc/freeswitch/')
            assert root.exists(), 'No root configuration dir found'
        return root


def manage(host, fscli=None, cache_key_pw=True, **ssh_opts):
    """Return a ``ConfigManager`` for the FreeSWITCH process
    discovered at ``host``.
    """
    ssh_opts['pkey'] = get_pkey(ssh_opts['keyfile']) if cache_key_pw else None
    # yes this is how we do everything remotely
    ssh = get_ssh(host, **ssh_opts)
    sftp = get_sftp(host, **ssh_opts)

    if not fscli:
        fscli = cli(ssh)

    # try to discover the base configuration dir
    try:
        runpath = fscli('global_getvar base_dir')
    except CLIConnectionError:
        raise CLIConnectionError(
            "Unable to access fs_cli at {}".format(host)
        )

    confpath = find_root(ssh, fscli, runpath)
    return manage_config(str(confpath), sftp, fscli, log)
