# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
conffs: A Python ORM API for configuring and managing FreeSWITCH
        configuration using Python data structures.
"""
import logging
import plumbum
import tempfile
import contextlib
import os
from io import BytesIO
from .comms import get_ssh, get_sftp, get_pkey
from .manage import manage_config, cli, CLIConnectionError, CLIError


__package__ = 'conffs'
__version__ = '0.1.alpha'
__author__ = ('Sangoma Technologies', 'tgoodlet@sangoma.com')
__all__ = ['find_root', 'manage', 'manage_config']


log = logging.getLogger('conffs')


def find_root(shell, fscli):
    '''Find and return the root configuration directory
    for the managed FreeSWITCH process.
    '''
    try:
        return shell.path(fscli('global_getvar', 'conf_dir'))
    except CLIError:
        # try to discover the base configuration dir
        try:
            runpath = fscli('global_getvar base_dir')
        except CLIConnectionError:
            raise CLIConnectionError("Unable to access fs_cli")
        # older versions of fs do not support the `conf_dir` var
        # so rely on the provided runtime path.
        root = shell.path(runpath).join('conf')
        if not root.exists():
            # a system packaged version?
            root = shell.path('/etc/freeswitch/')
            assert root.exists(), 'No root configuration dir found'
        return root


class SFTPFileIO(object):
    def __init__(self, sftp):
        self.sftp = sftp
        self.path = None

    @contextlib.contextmanager
    def open(self, mode='r'):
        # TODO: if opened in write mode, push changes to the remote file
        _, localpath = tempfile.mkstemp(
            prefix='{}-freeswitch-'.format(self.sftp._fqhost),
            suffix='.xml',
        )
        # copy to a local path for speed
        with open(localpath, 'wb') as localfile:  # open as bytes
            # copy locally
            self.sftp.getfo(self.path, localfile)
        with open(localpath, mode) as localfile:
            yield localfile

    def write(self, data, path=None):
        assert self.path, "Must set the filepath first"
        self.sftp.putfo(BytesIO(data), path or self.path)

    def copy(self, dst):
        self.sftp.copy(self.path, dst)

    def __call__(self, path):
        self.path = path
        return self


def manage(mode='local', confdir=None, docker=False, **kwargs):
    """Return a ``conffs.Client`` for managing a FreeSWITCH process.
    """
    if mode == 'ssh':
        host = kwargs['host']
        kwargs['pkey'] = get_pkey(
            kwargs['keyfile']) if kwargs['cache_key_pw'] else None
        shell = get_ssh(host, **kwargs)
        io = SFTPFileIO(get_sftp(host, **kwargs))

    elif mode == 'local':
        shell = plumbum.local
        io = plumbum.local.path
    else:
        raise ValueError("Unsupported mode '{}'".format(mode))

    if docker:
        cid = kwargs.get('container_id')
        if not cid:
            raise ValueError(
                "When connecting to a docker container you must provide "
                "a `container_id`"
            )
        fscli = cli(shell, prefix=('docker', 'container', 'exec', '-t', cid))
    else:
        fscli = cli(shell)

    confdir = confdir or find_root(shell, fscli)
    fsxmlpath = os.path.join(confdir, 'freeswitch.xml')
    conf_io = io(fsxmlpath)
    return manage_config(str(fsxmlpath), conf_io, fscli, log)
