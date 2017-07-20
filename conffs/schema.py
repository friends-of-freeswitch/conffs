"""
Schema to describe which object-relational mappings should be used
for each FreeSWITCH XML configuration "section".
"""
import time
import logging
from collections import namedtuple
from .orms import (
    TagMap, ElemMap, SpecialAttrsMap, AttrMap, ElemList
)


log = logging.getLogger('conffs')


_sections = []
_apis = {}


def section(**kwargs):
    """Decorator for registering config schema with meta data to be matched
    against when a config file is loaded.
    """
    def inner(cls):
        _sections.append((
            lambda d: any(d[key] == value for key, value in kwargs.items()),
            cls
        ))
        cls.modeldata = kwargs
        return cls

    return inner


def get_section(**kwargs):
    """Retrieve a section matching provided meta data.
    """
    for f, cls in _sections:
        if f(kwargs):
            return cls

    return TagMap


def api(modname):
    """Mark a class as being an api module.
    """
    def inner(cls):
        _apis[modname] = cls
        return cls

    return inner


class SofiaProfile(TagMap):
    schema = {
        'settings': {
            'maptype': SpecialAttrsMap,
            'tag': 'param',
        },
        'aliases': {
            'maptype': ElemList,
            'tag': 'alias',
        },
        'gateways': {
            'maptype': ElemMap,
            'path': 'gateways',
            'tag': 'gateway',
        },
        'gateways.params': {
            'maptype': SpecialAttrsMap,
            'path': '.',
            'tag': 'param',
        },
        'domains': {
            'maptype': ElemMap,
            'tag': 'domain',
        },
        'domains.domain': {
            'maptype': AttrMap,
            'path': '.',
            'tag': '.',
            'skipkeys': ['name'],
        },
    }


@section(
    xpath='section/configuration[@name="sofia.conf"]',
    modname='sofia',
)
class SofiaConf(TagMap):
    """A schema for sip profile config files
    """
    schema = {
        'global_settings': {
            'maptype': SpecialAttrsMap,
            'tag': 'param',
        },
        'profiles': {
            'maptype': ElemMap,
            'path': 'profiles',
            'tag': 'profile',
        },
        'profiles.profile': {
            'maptype': SofiaProfile,  # see subschema
            'path': '.',
            'tag': '.',
        },

    }


@api(modname='sofia')
class SofiaApi(object):
    """An API around ``mod_sofia``.
    """
    def __init__(self, client):
        self.client = client
        self.log = log.getChild('sofia')

    def start(self, name, timeout=11):
        """Start this sofia profile.
        If not started within ``timeout`` seconds, raise an error.
        """
        start = time.time()
        self.log.info("starting profile '{}'".format(name))
        self.client.cli('sofia', 'profile', name, 'start',
                        checkfail=lambda out: 'Failure'in out)
        # poll for profile to come up
        while 'Invalid Profile' in self.client.cli(
            'sofia', 'status', 'profile', name
        ):
            time.sleep(0.5)
            if time.time() - start > timeout:
                raise RuntimeError(
                    "Failed to start '{}' after {} seconds".format(
                        name, timeout)
                )

    def restart(self, name):
        self.log.info("restarting profile '{}'".format(name))
        self.client.cli('sofia', 'profile', name, 'restart',
                        checkfail=lambda out: 'Failure'in out)
        # poll for profile to come up
        while 'Invalid Profile' in self.client.cli(
            'sofia', 'status', 'profile', name
        ):
            time.sleep(0.5)

    def stop(self, name, timeout=12):
        """Stop this sofia profile.
        If not stopped within ``timeout`` seconds, raise an error.
        """
        start = time.time()
        self.log.info("stopping profile '{}'".format(name))
        self.client.cli('sofia', 'profile', name, 'stop',
                        checkfail=lambda out: 'Failure'in out)

        # poll for profile to shut down
        while 'Invalid Profile' not in self.client.cli(
            'sofia', 'profile', name, 'stop',
            checkfail=lambda out: 'Failure' in out
        ):
            time.sleep(1)
            if time.time() - start > timeout:
                raise RuntimeError(
                    "Failed to stop '{}' after {} seconds".format(
                        name, timeout)
                )

    def register(self, name, gateway):
        self.client.cli(
            'sofia', 'profile', name, 'register', gateway,
            checkgw=lambda out: 'Invalid gateway!' in out
        )

    def unregister(self, name, gateway):
        self.client.cli(
            'sofia', 'profile', name, 'unregister', gateway,
            checkgw=lambda out: 'Invalid gateway!' in out
        )

    def status(self):
        """Return status data from sofia in a nicely organized dict.
        """
        # remove '===' "lines"
        lines = [
            line for line in self.client.cli('sofia', 'status').splitlines()
            if '===' not in line]
        # pop summary line
        lines.pop(-1)

        # build component to status maps
        profiles = {}
        gateways = {}
        aliases = {}

        colnames = [name.lower() for name in lines.pop(0).split()]
        iname = colnames.index('name')
        colnames.remove('name')
        for line in lines:
            fields = [field.strip() for field in line.split('\t')]
            name = fields.pop(iname)
            row = {k.lower(): v for k, v in zip(colnames, fields)}
            tp = row.pop('type')
            if tp == 'profile':
                profiles[name] = row
            elif tp == 'gateway':
                profname, gwname = name.split("::")
                row['profile'] = profname
                gateways[gwname] = row
            elif tp == 'alias':
                aliases[name] = row

        return {'profiles': profiles, 'gateways': gateways, 'aliases': aliases}


@section(
    xpath='section[@name="dialplan"]',
    modname='dialplan',
)
class Dialplan(ElemMap):
    tag = 'context'
    schema = {
        'extensions': {
            'maptype': ElemMap,
            'path': '.',
            'tag': 'extension',
        },
        'extensions.conditions': {
            'maptype': TagMap,
            'path': 'condition',
            'tag': 'condition',
        },
        'extensions.conditions.condition': {
            'path': '.',
            'tag': '.',
            'maptype': AttrMap,
        },
        'extensions.conditions.actions': {
            'path': '.',
            'tag': 'action',
            'maptype': AttrMap,
        },
        'extensions.conditions.condition.anti-actions': {
            'path': '.',
            'tag': 'anti-action',
            'maptype': AttrMap,
        }
    }


@api(modname='directory')
class DirectoryApi(object):
    """An api around the directory subsystem.
    """
    def __init__(self, client):
        self.client = client

    def get_users(self, **kwargs):
        """Return all directory users in a map keyed by domain name.
        """
        args = []
        allowed = ('domain', 'group', 'user', 'context')
        for argname, value in kwargs.items():
            if argname not in allowed:
                raise ValueError(
                    '{} is not a valid argument to list_users'.format(
                        argname)
                )
            args.append('{} {}'.format(argname, value))

        # last two lines are entirely useless
        res = self.client.cli('list_users', *args).splitlines()[:-2]
        UserEntry = namedtuple("UserEntry", res[0].split('|'))
        # collect and pack all users
        users = []
        for row in res[1:]:
            users.append(UserEntry(*row.split('|')))

        # pack users by domain
        domains = {}
        for user in users:
            domains.setdefault(user.domain, []).append(user)

        return domains


@section(
    xpath='section[@name="directory"]',
    modname='directory'
)
class Directory(ElemMap):
    """A schema for a "domains".
    """
    tag = 'domain'
    schema = {
        'domain': {
            'maptype': TagMap,
            'path': '.',
            'tag': 'domain',
        },
        'domain.params': {
            'maptype': SpecialAttrsMap,
            'path': 'params',
            'tag': 'param',
        },
        'domain.variables': {
            'maptype': SpecialAttrsMap,
            'path': 'variables',
            'tag': 'variable',
        },
        'domain.groups': {
            'maptype': ElemMap,
            'tag': 'group',
        },
        'domain.groups.group': {
            'maptype': TagMap,
            'path': '.',
            'tag': '.',
        },
        'domain.groups.group.users': {
            'maptype': ElemMap,
            'tag': 'user',
            'keyattr': 'id',
        },
        'domain.groups.group.users.user': {
            'maptype': TagMap,
            'path': '.',
            'tag': '.',
        },
        'domain.groups.group.users.user.params': {
            'maptype': SpecialAttrsMap,
            'tag': 'param',
            'keyattr': 'name',
        },
        'domain.groups.group.users.user.variables': {
            'maptype': SpecialAttrsMap,
            'path': 'variables',
            'tag': 'variable',
        },
        'domain.groups.group.users.user.gateways': {
            'maptype': ElemMap,
            'path': 'gateways',
            'tag': 'gateway',
        },
        'domain.groups.group.users.user.gateways.gateway': {
            'maptype': SpecialAttrsMap,
            'path': '.',  # kv store off of users
            'tag': 'param',
        },
    }


@section(
    xpath='section/configuration[@name="event_socket.conf"]',
    modname='event_socket',
)
class EventSocket(TagMap):
    path = '.'
    schema = {
        'settings': {
            'maptype': SpecialAttrsMap,
            'path': 'settings',
            'tag': 'param',
        },
    }
