#===============================================================================
# Copyright (C) 2014 Anton Vorobyov
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


import types
from collections import OrderedDict
from itertools import chain

from reverence.blue import DBRow
from reverence.carbon.common.script.sys.row import Row
from reverence.carbon.common.lib.utillib import KeyVal
from reverence.eve.common.script.sys.rowset import FilterRowset, IndexedRowLists, Rowset
from reverence.eve.common.script.universe.locationWrapper import SolarSystemWrapper
from reverence.fsd import FSD_Dict, _FixedSizeList as FSD_FixedSizeList, FSD_Index, FSD_NamedVector, FSD_Object


class EveNormalizer(object):
    """
    Class, which 'flattens' indexed structures into list of
    'rows' and converts all eve-specific data structures into
    python built-in types.
    """

    def run(self, eve_container):
        """
        Entry point for conversion jobs. Runs method which recursively
        changes contents of passed container to present them in pythonized
        data structures.
        """
        data = self._route_object(eve_container)
        return data

    def _route_object(self, obj):
        """
        Pick proper method for passed object and invoke it.
        """
        # Primitive objects do not need any conversion
        if type(obj) in self._primitives:
            return obj
        method = None
        # Try to find parent class for passed object, and if we
        # have any in our records - choose handler for it
        for candidate_class in self._conversion_classes:
            if isinstance(obj, candidate_class):
                method = self._conversion_classes[candidate_class]
                break
        if method is None:
            msg = 'unable to route {}'.format(type(obj))
            guid = getattr(obj, '__guid__', None)
            if guid is not None:
                msg = '{} (guid {})'.format(msg, guid)
            print(obj, self._pythonize_keyval(obj))
            raise UnknownContainerTypeError(msg)
        return method(self, obj)

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

    def _pythonize_filter_rowset(self, obj):
        """
        Filter rowsets are map-like objects, where keys are are some
        indices and values are lists of rows or indexed lists of rows,
        depending on parameters passed to it during initialization. We
        assume we do not need keys, thus everything is converted into
        single tuple.
        """
        # Process all sublists (they might be not usual, but e.g. rowsets),
        # then chain them together into single tuple
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
        indices and values are lists of rows. This is very similar to filter
        rowsets, thus we're reusing its conversion method.
        """
        return self._pythonize_filter_rowset(obj.values())

    def _pythonize_keyval(self, obj):
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

    _conversion_classes = OrderedDict([
        (FSD_Dict, _pythonize_map),
        (FSD_FixedSizeList, _pythonize_iterable),
        # FSD_MultiIndex is also FSD_Index subclass and have
        # iteritems() method
        (FSD_Index, _pythonize_map),
        (FSD_NamedVector, _pythonize_fsd_named_vector),
        (FSD_Object, _pythonize_fsd_object),
        (Row, _pythonize_row),
        (DBRow, _pythonize_dbrow),
        (FilterRowset, _pythonize_filter_rowset),
        # Rowset and IndexRowset (which is subclass of Rowset) support
        # regular iterable interface
        (Rowset, _pythonize_iterable),
        (IndexedRowLists, _pythonize_indexed_lists),
        # Built-in classes have lesser priority, as some custom
        # classes inherit from them
        (KeyVal, _pythonize_keyval),
        # SolarSystemWrapper is subclass of int, despite this
        # it's used to store some attributes, same way as KeyVal
        (SolarSystemWrapper, _pythonize_keyval),
        (dict, _pythonize_map),
        (list, _pythonize_iterable),
        (tuple, _pythonize_iterable)
    ])

    _primitives = (
        types.NoneType,
        types.BooleanType,
        types.FloatType,
        types.IntType,
        types.LongType,
        types.StringType,
        types.UnicodeType
    )


class UnknownContainerTypeError(Exception):
    """
    Raised when normalizer doesn't know what to do
    with passed object.
    """
    pass
