"""
XML schema which describe object-relational mappings for FreeSWITCH
configuration "sections".
"""
import time
import logging
from copy import deepcopy
from .orms import TagMap, ElemMap, SpecialAttrsMap, AttrMap, model


log = logging.getLogger('sandswitches')


def buildfromschema(obj, schemadict, **kwargs):
    # (initial) unbuilt section map type
    if isinstance(obj, type):
        obj = obj(
            name=obj.modeldata['id'],
            path=getattr(obj, 'path', '.'),
            tag=getattr(obj, 'tag', '.'),
            elem=kwargs['root'].xpath(obj.modeldata['xpath'])[0],
            **kwargs
        )
        schemadict = obj.schema

    if not schemadict:
        return

    # construct maps from schema
    subschema = {}
    subobjs = {}
    for attrpath, contents in schemadict.items():
        args = deepcopy(contents)
        name, _, tail = attrpath.partition('.')

        if tail:  # attrpath had at least one '.'
            subschema.setdefault(name, {})[tail] = args
        else:
            # apply maptype as attr
            cls = args.pop('maptype')

            subobj = cls(
                name=name,
                path=args.pop('path', attrpath),
                tag=args.pop('tag'),
                elem=obj.elem,
                confmng=obj.confmng,
                **args
            )
            # support maptype subclasses which define further schema
            if getattr(subobj, 'schema', None):
                buildfromschema(subobj, subobj.schema)

            subobjs[name] = subobj

            # every subobj can be accessed explicitly by attr name
            setattr(obj, name, subobj)
            if isinstance(obj, TagMap):
                obj.subtypes[name] = subobj

    if isinstance(obj, ElemMap):
        assert len(subobjs) == 1, "ElemMap must map to exactly one subsection"
        obj.valtype = subobj

    if subschema:  # recursively build from subschema
        for name, subobj in subobjs.iteritems():
            subcontents = subschema.get(name)
            if subcontents:
                buildfromschema(subobj, subcontents)

    return obj


class SofiaProfile(TagMap):
    schema = {
        'settings': {
            'maptype': SpecialAttrsMap,
            'tag': 'param',
        },
        'aliases': {
            'maptype': SpecialAttrsMap,
            'path': '.',
            'tag': 'param',
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

    def start(self, timeout=10):
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

    def stop(self, timeout=10):
        start = time.time()
        log.info("stopping profile '{}'".format(self.key))
        self.confmng.fscli('sofia', 'profile', self.key, 'stop',
                           checkfail=lambda out: 'Failure'in out)
        # poll for profile to come up
        while 'Invalid Profile' not in self.confmng.fscli(
            'sofia', 'profile', self.key, 'stop',
            checkfail=lambda out: 'Failure' in out
        ):
            time.sleep(0.5)
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
