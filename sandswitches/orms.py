# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
Object-relational mappings for common XML schema patterns found in a variety
of sections.
"""
import logging
from collections import MutableMapping
from copy import deepcopy
from lxml import etree


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


class KeyValues(MutableMapping):

    kwargs = {}

    def __init__(self, name, path, tag, elem, confmng, **kwargs):
        self.name = name
        self.path = path  # relative xpath
        self.tag = tag
        self.elem = elem
        self.confmng = confmng
        self.attrs = set()
        kwds = deepcopy(type(self).kwargs)
        kwds.update(kwargs)
        self.kwargs = kwds
        # apply defaults
        for key, val in kwds.items():
            setattr(self, key, val)

    def fromelem(self, key, elem):
        kwargs = {}
        for attr in self.kwargs:
            kwargs[attr] = getattr(self, attr)
        kwargs['key'] = key
        inst = type(self)(
            self.name, self.path, self.tag, elem, self.confmng, **kwargs
        )
        for name in self.attrs:
            setattr(inst, name, getattr(self, name))
        return inst

    def __repr__(self):
        return '{}({})'.format(self.name, repr(dict(self)))

    def _buildrent(self):
        node = self.elem
        for elem in self.path.split('/'):
            if node.find(elem) is None:
                etree.SubElement(node, elem)

    @property
    def parent(self):
        """The XML parent element for this map pattern.
        """
        if self.path == '.':
            return self.elem

        rent = self.elem.find(self.path)
        if rent is None:
            self._buildrent()

        rent = self.elem.find(self.path)
        assert rent is not None
        return rent

    @property
    def epath(self):
        return self.confmng.etree.getelementpath(self.elem)

    @property
    def xpath(self):
        return self.confmng.etree.getpath(self.elem)

    def toxmlstring(self):
        return etree.tostring(self.parent, pretty_print=True)

    def printxml(self):
        print(self.toxmlstring())

    def __deepcopy__(self, memo):
        return self.fromelem(self.key, deepcopy(self.elem))

    def appendfrom(self, key, src):
        """Append a copy of the value at ``src`` to the value at ``key``.
        """
        val = self[src]
        newval = deepcopy(val)
        self[key] = newval
        # TODO: why the hell do we do this instead of `return newval` again?
        return self[key]

    def appendfromxml(self, xmlstr, keyattr='name'):
        tree = etree.XML(xmlstr)
        if tree.tag == 'include':
            children = tree.getchildren()
            assert len(children) == 1
            tree = children[0]
        self.elem.append(tree)
        return self[tree.attrib[keyattr]]


class AttrMap(KeyValues):
    """Access maps of element attributes as if a dict:

    <domain name="upreg" alias="false" parse="true"/>

    becomes something like,

    >>> domain['name']
    "upreg"
    """
    kwargs = {
        'skipkeys': []
    }

    @property
    def _attribs(self):
        path = '/'.join((self.path, self.tag))
        nodes = self.elem.xpath(path)
        assert len(nodes) == 1, "Not an AttrMap?"
        return nodes[0].attrib

    def __iter__(self):
        return (key for key in self._attribs.iterkeys()
                if key not in self.skipkeys)

    def __len__(self):
        return len(set(self._attribs.keys()) - set(self.skipkeys))

    def __getitem__(self, key):
        if key in self.skipkeys:
            raise KeyError(key)
        return self._attribs[key]

    def __setitem__(self, key, value):
        if key in self.skipkeys:
            raise KeyError(key)
        self._attribs[key] = value

    def __delitem__(self, key):
        if key in self.skipkeys:
            raise KeyError(key)
        del self._attribs[key]


class SpecialAttrsMap(KeyValues):
    """A wrapper for a group of multiple identically named elements but which
    store a map in element attributes. As an example in FS configs we often
    see repeated sections like,

    <settings>
      <param name='doggy' value='dog'/>
      <param name='kitty' value='cat'/>
    <settings/>

    and we want to be able to operate on the section as if it were a dict.
    >>> settings['doggy']
    'dog'
    """
    kwargs = {
        'keyattr': 'name',
        'valattr': 'value',
    }

    def _getelem(self, key):
        try:
            return self.elem.xpath(
                '{}/{}[@{}="{}"]'.format(
                    self.path, self.tag, self.keyattr, key))[0]
        except IndexError:
            raise KeyError(key)

    def __iter__(self):
        elems = self.elem.xpath('{}/{}[@{}]'.format(
            self.path, self.tag, self.keyattr))
        return (e.attrib[self.keyattr] for e in elems)

    def __len__(self):
        return len(self.elem.xpath('{}/{}[@{}]'.format(
            self.path, self.tag, self.keyattr)))

    def __getitem__(self, key):
        return self._getelem(key).attrib[self.valattr]

    def __setitem__(self, key, value):
        try:
            node = self._getelem(key)
            node.attrib[self.valattr] = value
        except KeyError:
            # insert new element using the last part of the initial path
            # as the tag label
            etree.SubElement(
                self.parent, self.tag,
                **{self.keyattr: key, self.valattr: str(value)}
            )

    def __delitem__(self, key):
        node = self._getelem(key)
        node.getparent().remove(node)


class ElemMap(KeyValues):
    """A represent a collection of key-tree pairs as a dict.
    Turns this,

        <groups>
            <group name='default'>
                ... XML sub-tree ...
            <group/>
        <groups/>

    into this,
        >>> groups['default']
        <XML sub-tree wrapper obj>
    """
    kwargs = {
        'valtype': None,
        'keyattr': 'name',
    }

    def _getelem(self, key):
        try:
            if isinstance(key, str):
                return self.elem.xpath(
                    '{}/{}[@{}="{}"]'.format(
                        self.path, self.tag, self.keyattr, key))[0]
            # int index
            return self.elem.xpath('{}/{}[@{}]'.format(
                self.path, self.tag, self.keyattr))[key]

        except IndexError:
            raise KeyError(key)

    def __iter__(self):
        elems = self.elem.xpath('{}/{}'.format(self.path, self.tag))
        return (e.attrib[self.keyattr] for e in elems)

    def __len__(self):
        return len(self.elem.xpath('{}/{}'.format(self.path, self.tag)))

    def __getitem__(self, key):
        # this is subtle, the valtype will have it's elem reassigned
        # depending on which subtree is accessed
        return self.valtype.fromelem(key, self._getelem(key))

    def __setitem__(self, key, value):
        value = dict(value)
        try:
            val = self[key]
            val.clear()  # delete all conents
        except KeyError:
            # insert new element (ex. <tag name='foo'>)
            node = etree.SubElement(
                self.parent, self.tag, **{self.keyattr: key}
            )
            val = self.valtype.fromelem(key, node)

        val.update(value)

    def __delitem__(self, key):
        node = self._getelem(key)
        node.getparent().remove(node)


class TagMap(KeyValues):
    '''Takes sections like this,

    <doggy>
      <kitty>
        .. xml stuff ..
      </kitty>
      <hamburger>
        .. holy shit more xml stuff ..
      </hamburger>
    </doggy>

    and transforms it to this,
    >>> doggy['kitty']
    <XML sub-tree wrapper obj>

    `subtypes` is used to look up the value wrapper to apply on the
    retrieved xml sub-tree.
    '''
    kwargs = {
        'subtypes': {},
    }

    def __len__(self):
        return len(self.subtypes)

    def __iter__(self):
        return (key for key in self.subtypes.iterkeys()
                if self.elem.find(key) is not None)

    def _getelem(self, key):
        try:
            return self.elem.xpath(key)[0]
        except IndexError:
            raise KeyError(key)

    def __getitem__(self, key):
        subtype = self.subtypes[key]
        self._getelem(subtype.path)
        return subtype.fromelem(key, self.elem)

    def __setitem__(self, key, value):
        value = dict(value)
        try:
            val = self[key]
            val.clear()  # delete all conents
        except KeyError:
            subtype = self.subtypes[key]
            # pass our parent elem to a new subtype inst
            val = subtype.fromelem(key, self.parent)

        val.update(value)

    def __delitem__(self, key):
        self.elem.remove(self._getelem(key))
