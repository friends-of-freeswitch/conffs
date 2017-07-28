# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
Object-relational mappings for common XML schema patterns found in a variety
of sections.
"""
import logging
from collections import MutableMapping, MutableSequence
from copy import deepcopy
from lxml import etree


log = logging.getLogger('conffs')


class EtreeMapper(object):
    """Access the etree using the xpath API.
    """
    # A shitty mechanism to pass instance variable state into new instances
    kwargs = {}

    def __init__(self, name, path, tag, elem, client, **kwargs):
        self.name = name
        self.path = path  # relative xpath
        self.tag = tag
        # This is the highest level node in the etree that we have a
        # reference to. It is not necessarily the "parent" etree element of
        # the underlying mapping. It is some node in the etree above the XML
        # section of concern which when combined with self.path points to the
        # "parent" etree element.
        self.elem = elem
        self.client = client
        self.attrs = set()
        kwds = deepcopy(type(self).kwargs)
        kwds.update(kwargs)
        self.kwargs = kwds
        # apply defaults
        for key, val in kwds.items():
            setattr(self, key, val)

    def fromelem(self, key, elem):
        """Create and return an instance of this type to wrap the provided
        etree element. Copy into it the instance variables defined in
        self.kwargs.
        """
        kwargs = {}
        for attr in self.kwargs:
            kwargs[attr] = getattr(self, attr)
        kwargs['key'] = key  # adds a self.key attr to the new inst
        inst = type(self)(
            self.name, self.path, self.tag, elem, self.client, **kwargs
        )
        for name in self.attrs:
            setattr(inst, name, getattr(self, name))
        return inst

    def _buildparent(self):
        """Build all etree elements that don't exist up to ``self.path``
        (which defines the parent node for this mapper type).
        """
        node = self.elem
        for elem in self.path.split('/'):
            if node.find(elem) is None:
                etree.SubElement(node, elem)

    @property
    def parent(self):
        """The etree "parent" element for this mapping/section (i.e. the
        element which either defines or whose sub-elements define the keys in
        the mapping).
        """
        if self.path == '.':
            return self.elem

        parent = self.elem.find(self.path)
        if parent is None:
            self._buildparent()

        parent = self.elem.find(self.path)
        assert parent is not None
        return parent

    @property
    def epath(self):
        """The element path to ``self.elem``.
        """
        return self.client.etree.getelementpath(self.elem)

    @property
    def xpath(self):
        """The xpath to ``self.elem``.
        """
        return self.client.etree.getpath(self.elem)

    def toxmlstring(self):
        """Render this mapping to an XML string.
        """
        return etree.tostring(self.parent, pretty_print=True)

    def printxml(self):
        """Print the this mapping as rendered XML to stdout.
        """
        print(self.toxmlstring().decode())

    def __deepcopy__(self, memo):
        return self.fromelem(self.key, deepcopy(self.elem))

    def appendfrom(self, src, key):
        """Append a copy of the value at ``src`` to the value at ``key``.
        """
        val = self[src]
        newval = deepcopy(val)
        self[key] = newval
        # The reason we return this instead of newval is that some
        # __getitem__() calls create a new wrapper instance using fromelem()
        # which applies state to the new obj (such as self.key). So returning
        # this ensures that:
        # obj.appendfrom('newkey', 'key') is obj['newkey'] == True
        return self[key]

    def appendfromxml(self, xmlstr, keyattr='name'):
        tree = etree.XML(xmlstr.encode())
        if tree.tag == 'include':
            children = tree.getchildren()
            assert len(children) == 1
            tree = children[0]
        self.elem.append(tree)
        return self[tree.attrib[keyattr]]


class KeyValues(MutableMapping, EtreeMapper):
    """An object to XML mapper base type which makes a key-value store
    encoded in XML quack like an ordered mapping.
    """
    def __repr__(self):
        return '{}({})'.format(self.name, repr(dict(self)))


class Sequence(MutableSequence, EtreeMapper):
    """An object to XML mapper base type which makes a list of elements
    encoded in XML quack like an sequence.
    """
    def __repr__(self):
        return '{}({})'.format(self.name, repr(list(self)))


class ElemList(Sequence):
    """Access ordered lists of elements which define a single value in
    in an attribute named ``attrname``. In other words it transforms XML
    like:

    <aliases>
        <alias name="outbound"/>
        <alias name="nat"/>
    </aliases>

    into a sequence like:

    >>> sofia.profiles['external'].aliases
    ["outbound", "nat"]

    >>> sofia.profiles['external'].aliases.append('doggy')
    ["outbound", "nat", "doggy"]
    """
    kwargs = {
        'attrname': 'name'
    }

    @property
    def _subelems(self):
        return self.elem.xpath('/'.join((self.path, self.tag)))

    def __getitem__(self, index):
        return self._subelems[index].attrib[self.attrname]

    def __setitem__(self, index, value):
        self._subelems[index].attrib[self.attrname] = value

    def __delitem__(self, index):
        del self.parent[index]

    def __len__(self):
        return len(self._subelems)

    def insert(self, index, value):
        self.parent.insert(
            index,
            etree.Element(self.tag, **{self.attrname: value})
        )

    # for compat with mapping types which use this as a sub-type mapper
    update = Sequence.extend


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
    def _subelems(self):
        return self.elem.xpath('/'.join((self.path, self.tag)))

    @property
    def _attribs(self):
        nodes = self._subelems
        assert len(nodes) == 1, "Not an AttrMap? Nodes are {}".format(nodes)
        return nodes[0].attrib

    def __iter__(self):
        if not self._subelems:
            return iter([])
        return (key for key in self._attribs.keys()
                if key not in self.skipkeys)

    def __len__(self):
        if not self._subelems:
            return 0
        return len(set(self._attribs.keys()) - set(self.skipkeys))

    def __getitem__(self, key):
        if key in self.skipkeys:
            raise KeyError(key)
        return self._attribs[key]

    def __setitem__(self, key, value):
        if key in self.skipkeys:
            raise KeyError(key)
        try:
            self._attribs[key] = value
        except IndexError:
            etree.SubElement(self.parent, self.tag, **{key: value})

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
        # attributes whose values define the keys and values in the
        # underlying mapping
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
    """Represent a collection of key-tree pairs as a dict.
    Turns this,

        <groups>
            <group name='default'>
                ... XML sub-tree ...
            <group/>
        <groups/>

    into this,
        >>> groups['default']
        <XML sub-tree mapper obj>
    """
    kwargs = {
        # The KeyValues subtype used to wrap access to underlying XML subtrees
        # which are the values of this mapping.
        'valtype': None,
        'keyattr': 'name',
    }

    def _getelem(self, key):
        try:
            if isinstance(key, int):
                return self.elem.xpath('{}/{}[@{}]'.format(
                    self.path, self.tag, self.keyattr))[key]
            else:  # str index
                return self.elem.xpath(
                    '{}/{}[@{}="{}"]'.format(
                        self.path, self.tag, self.keyattr, key))[0]
        except IndexError:
            raise KeyError(key)

    def __iter__(self):
        elems = self.elem.xpath('{}/{}'.format(self.path, self.tag))
        return (e.attrib[self.keyattr] for e in elems)

    def __len__(self):
        return len(self.elem.xpath('{}/{}'.format(self.path, self.tag)))

    def __getitem__(self, key):
        # This is subtle, `valtype` will be assigned to an object mapper
        # externally from the `buildfromschema` function and can be assigned to
        # at most one type. In other words you should never see more then one
        # child sub-mapper object defined under an ElemMap in a section's
        # schema.
        return self.valtype.fromelem(key, self._getelem(key))

    def __setitem__(self, key, value):
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
    <XML sub-tree mapper obj>

    `subtypes` is used to look up the object-mapper to apply on the
    retrieved XML sub-tree.
    '''
    kwargs = {
        'subtypes': {},
    }

    def __len__(self):
        return len(self.subtypes)

    def __iter__(self):
        return (key for key in self.subtypes.keys()
                if self.elem.find(key) is not None)

    def _getelem(self, key):
        try:
            return self.elem.xpath(key)[0]
        except IndexError:
            raise KeyError(key)

    def __getitem__(self, key):
        subtype = self.subtypes[key]
        # make sure an etree element exists
        self._getelem(subtype.path)
        return subtype.fromelem(key, self.elem)

    def __setitem__(self, key, value):
        try:
            val = self[key]
            val.clear()  # delete all conents
        except KeyError:
            # lookup the correct sub-mapping type for this ``key``
            subtype = self.subtypes[key]
            # insert new element (ex. <tag/>)
            etree.SubElement(self.parent, subtype.path)
            val = subtype.fromelem(key, self.parent)

        val.update(value)

    def __delitem__(self, key):
        self.elem.remove(self._getelem(key))


def buildfromschema(obj, schemadict, **kwargs):
    """Given an XML schema-to-object description, build a tree of object mappers
    which can be used to create and modify underlying XML structures.
    """
    # Initial unbuilt section type (i.e. anything marked as a "schema.model").
    if isinstance(obj, type):
        obj = obj(
            name=obj.modeldata['modname'],
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
                client=obj.client,
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
        for name, subobj in subobjs.items():
            subcontents = subschema.get(name)
            if subcontents:
                buildfromschema(subobj, subcontents)

    return obj
