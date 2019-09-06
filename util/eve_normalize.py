#===============================================================================
# Copyright (C) 2014-2019 Anton Vorobyov
#
# This file is part of Phobos.
#
# Phobos is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Phobos is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Phobos. If not, see <http://www.gnu.org/licenses/>.
#===============================================================================


import inspect
import types
from collections import OrderedDict
from itertools import chain

from reverence.carbon.common.script.sys.row import Row


class EveNormalizer(object):
    """
    Class, which 'flattens' indexed structures into list of
    'rows' and converts all eve-specific data structures into
    python built-in types.
    """

    def __init__(self):
        self._loader_module = None

    def run(self, eve_container, loader_module=None):
        """
        Entry point for conversion jobs. Runs method which recursively
        changes contents of passed container to present them in pythonized
        data structures.
        """
        self._loader_module = loader_module
        data = self._route_object(eve_container)
        return data

    def _route_object(self, obj):
        """
        Pick proper method for passed object and invoke it.
        """
        # Primitive objects do not need any conversion
        if type(obj) in self._primitives:
            return obj
        # Try strict class/guid matching first
        cls = type(obj)
        try:
            method = self._class_match[cls]
        except KeyError:
            pass
        else:
            return method(self, obj)
        # __guid__ is available for many objects exposed by reverence,
        # use class name as fallback only when it's not available
        cls_name = getattr(obj, '__guid__', type(obj).__name__)
        try:
            method = self._name_match[cls_name]
        except KeyError:
            pass
        else:
            return method(self, obj)
        # Try to find parent class for passed object, and if we
        # have any in our records - run handler for it
        for candidate_cls in self._subclass_match:
            if isinstance(obj, candidate_cls):
                method = self._subclass_match[candidate_cls]
                return method(self, obj)
        # Stuff specific to FSD binary format
        if self._loader_module is not None:
            # Check if class is defined in passed loader, if it is, then
            # we're dealing with FSD binary item for certain
            if inspect.getmodule(type(obj)) is self._loader_module:
                return self.pythonize_fsdbinary_item(obj)
            # FSD contains bunch of vector classes which are defined outside of
            # loader (shown as defined in builtins), process them separately
            if type(obj).__name__.endswith('_vector'):
                return self.pythonize_fsdbinary_item(obj, ignore_attrs=(
                    'n_fields', 'n_sequence_fields', 'n_unnamed_fields'))
        # If we got here, routing failed
        msg = 'unable to route {}'.format(type(obj))
        guid = getattr(obj, '__guid__', None)
        if guid is not None:
            msg = '{} (guid {})'.format(msg, guid)
        raise UnknownContainerTypeError(msg)

    def _pythonize_iterable(self, obj):
        """
        For objects which have access interface similar to python
        iterables - convert contents and return them as tuple.
        """
        return tuple(self._route_object(i) for i in obj)

    def _pythonize_map(self, obj):
        """
        For objects which have access interface similar to python
        dictionaries - convert keys and values and return as dict.
        """
        container = {}
        for key, value in obj.iteritems():
            proc_key = self._route_object(key)
            proc_value = self._route_object(value)
            container[proc_key] = proc_value
        return container

    def _pythonize_string(self, obj):
        """
        Sometimes EVE has non-ASCII symbols in non-unicode strings,
        default encoding for these is cp1252, here we ensure they are
        converted to unicode so we don't have to run any additional
        processing on them elsewhere.
        """
        return obj.decode('cp1252')

    def _pythonize_dbrow(self, obj):
        """
        DBRow can be converted into dictionary - its keys are
        accessed via hidden '__keys__' attribute (implementation
        detail, ideally we should fetch it from container's
        .header attribute).
        """
        container = {}
        for key in obj.__keys__:
            value = obj[key]
            proc_key = self._route_object(key)
            proc_value = self._route_object(value)
            container[proc_key] = proc_value
        return container

    def _pythonize_list_of_iterables(self, obj):
        """
        Here we suppose that passed object is list of iterables of
        any type; we process all of these iterables, and then
        concatenate them to form a single tuple.
        """
        return tuple(chain(*(self._route_object(l) for l in obj)))

    def _pythonize_fsd_named_vector(self, obj):
        """
        Named vectors resemble tuples/lists, but contain name data for
        their fields, thus we convert them into dicts.
        """
        container = {}
        name_data = obj.schema['aliases']
        for name, index in name_data.items():
            value = obj.data[index]
            proc_name = self._route_object(name)
            proc_value = self._route_object(value)
            container[proc_name] = proc_value
        return container

    def _pythonize_fsd_object(self, obj):
        """
        FSD_Object is similar to regular python objects - but unlike them,
        list of accessible attributes is stored in 'attributes' attribute.
        """
        container = {}
        for key in obj.attributes:
            # Sometimes values are missing
            value = getattr(obj, key, None)
            proc_key = self._route_object(key)
            proc_value = self._route_object(value)
            container[proc_key] = proc_value
        return container

    def _pythonize_indexed_lists(self, obj):
        """
        Indexed lists are represented as dictionary, where keys are some
        indices and values are lists of rows. This is very similar to list
        of iterables, thus we're reusing its conversion method.
        """
        return self._pythonize_list_of_iterables(obj.values())

    def _pythonize_indexed_rows(self, obj):
        """
        Regular map, where values are data rows, and keys are some
        values taken from the rows they correspond to.
        """
        return self._pythonize_iterable(obj.values())

    def _pythonize_pyobj(self, obj):
        """
        KeyVal is a python-like object, where attributes/values are stored
        as object attributes.
        """
        return self._pythonize_map(obj.__dict__)

    def _pythonize_row(self, obj):
        """
        Row objects are tricky part for phobos - they expose convenient
        interface to user, which is 'improved' by reverence to provide things
        like out-of-the-box string localization, or object references (e.g.
        group row provides reference to actual category row, not just
        categoryID). Reverence is known to break on some of these 'improvements'
        (e.g. RamDetail class). This can be worked around in quite a dirty
        way, but as we do not really need any of these improvements - we
        take 'raw' row (DBRow) from Row (and its subclasses) and use it,
        ignoring everything built on top of it.
        """
        return self._pythonize_dbrow(obj.line)

    def pythonize_fsdbinary_item(self, obj, ignore_attrs=()):
        item = {}
        for attr_name in dir(obj):
            if attr_name.startswith('__') and attr_name.endswith('__'):
                continue
            if attr_name in ignore_attrs:
                continue
            item[attr_name] = self._route_object(getattr(obj, attr_name))
        return item

    _primitives = (
        types.NoneType,
        types.BooleanType,
        types.FloatType,
        types.IntType,
        types.LongType,
        types.UnicodeType)

    _class_match = {
        types.StringType: _pythonize_string,
        types.ListType: _pythonize_iterable,
        types.TupleType: _pythonize_iterable}

    _name_match = {
        # Usually seen in cache
        'dbutil.CFilterRowset': _pythonize_indexed_lists,
        'dbutil.CIndexedRowset': _pythonize_indexed_rows,
        'dbutil.CRowset': _pythonize_iterable,
        'dbutil.RowDict': _pythonize_indexed_rows,
        'dbutil.RowList': _pythonize_iterable,
        # Conventional bulkdata classes
        'util.FilterRowset': _pythonize_list_of_iterables,
        'util.IndexedRowLists': _pythonize_indexed_lists,
        'util.IndexRowset': _pythonize_iterable,
        'util.KeyVal': _pythonize_pyobj,
        'util.Rowset': _pythonize_iterable,
        # FSD-related classes, usually seen in bulkdata
        'FSD_Dict': _pythonize_map,
        'FSD_MultiIndex': _pythonize_map,
        'FSD_NamedVector': _pythonize_fsd_named_vector,
        'FSD_Object': _pythonize_fsd_object,
        '_FixedSizeList': _pythonize_iterable,
        '_VariableSizedList': _pythonize_iterable,
        # FSD binary specific classes
        'dict': _pythonize_map,  # cfsd.dict
        'list': _pythonize_iterable,  # cfsd.list
        # Misc
        'blue.DBRow': _pythonize_dbrow,
        'universe.SolarSystemWrapper': _pythonize_pyobj}

    _subclass_match = OrderedDict([
        # Row is handled through isinstance check because reverence
        # actually provides its subclasses, but it doesn't make sense
        # to specify them all
        (Row, _pythonize_row),
        # Includes dictionaries and FSDLiteStorage
        (types.DictType, _pythonize_map)])


class UnknownContainerTypeError(Exception):
    """
    Raised when normalizer doesn't know what to do
    with passed object.
    """
    pass
