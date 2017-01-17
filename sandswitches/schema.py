"""
Schema to describe which object-relational mappings should be used
for each FreeSWITCH XML configuration "section".
"""
import time
import logging
from .orms import (
    TagMap, ElemMap, SpecialAttrsMap, AttrMap, ElemList
)


log = logging.getLogger('sandswitches')


_models = []


def model(**kwargs):
    """Decorator for registering config models with meta data to be matched
    against when a config file is loaded.
    """
    def inner(cls):
        _models.append((
            lambda d: any(d[key] == value for key, value in kwargs.items()),
            cls
        ))
        cls.modeldata = kwargs
        return cls

    return inner


def get_model(**kwargs):
    """Retrieve a model matching provided meta data.
    """
    for f, cls in _models:
        if f(kwargs):
            return cls

    return TagMap


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

    def start(self, timeout=11):
        """Start this sofia profile.
        If not started within ``timeout`` seconds, raise an error.
        """
        start = time.time()
        log.info("starting profile '{}'".format(self.key))
        self.confmng.fscli('sofia', 'profile', self.key, 'start',
                           checkfail=lambda out: 'Failure'in out)
        # poll for profile to come up
        while 'Invalid Profile' in self.confmng.fscli(
            'sofia', 'status', 'profile', self.key
        ):
            time.sleep(0.5)
            if time.time() - start > timeout:
                raise RuntimeError(
                    "Failed to start '{}' after {} seconds".format(
                        self.key, timeout)
                )

    def restart(self):
        log.info("restarting profile '{}'".format(self.key))
        self.confmng.fscli('sofia', 'profile', self.key, 'restart',
                           checkfail=lambda out: 'Failure'in out)
        # poll for profile to come up
        while 'Invalid Profile' in self.confmng.fscli(
            'sofia', 'status', 'profile', self.key
        ):
            time.sleep(0.5)

    def stop(self, timeout=12):
        """Stop this sofia profile.
        If not stopped within ``timeout`` seconds, raise an error.
        """
        start = time.time()
        log.info("stopping profile '{}'".format(self.key))
        self.confmng.fscli('sofia', 'profile', self.key, 'stop',
                           checkfail=lambda out: 'Failure'in out)

        # poll for profile to shut down
        while 'Invalid Profile' not in self.confmng.fscli(
            'sofia', 'profile', self.key, 'stop',
            checkfail=lambda out: 'Failure' in out
        ):
            time.sleep(1)
            if time.time() - start > timeout:
                raise RuntimeError(
                    "Failed to stop '{}' after {} seconds".format(
                        self.key, timeout)
                )

    def register(self, gateway):
        self.confmng.fscli(
            'sofia', 'profile', self.key, 'register', gateway,
            checkgw=lambda out: 'Invalid gateway!' in out
        )

    def unregister(self, gateway):
        self.confmng.fscli(
            'sofia', 'profile', self.key, 'unregister', gateway,
            checkgw=lambda out: 'Invalid gateway!' in out
        )


@model(
    xpath='section/configuration[@name="sofia.conf"]',
    id='sofia',
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


@model(
    xpath='section[@name="dialplan"]',
    id='dialplans',
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


@model(
    xpath='section[@name="directory"]',
    id='directory'
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


@model(
    xpath='section/configuration[@name="event_socket.conf"]',
    id='event_socket',
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
