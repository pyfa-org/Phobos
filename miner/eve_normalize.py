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


from itertools import chain


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
        obj_type = getattr(obj, '__guid__', type(obj).__name__)
        method = self._conversion_map[obj_type]
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

    def _pythonize_c_indexed_rowset(self, obj):
        """
        CIndexedRowset is dictionary-like container, where we
        need just values.
        """
        return self._pythonize_iterable(obj.values())

    def _pythonize_dbrow(self, obj):
        """
        DBRow is similar to python dictionary, but its keys are
        accessed via hidden '__header__' attribute.
        """
        container = {}
        for key in obj.__header__.Keys():
            value = obj[key]
            proc_key = self._route_object(key)
            proc_value = self._route_object(value)
            # Keys are assumed to be python primitives
            container[proc_key] = proc_value
        return container

    def _pythonize_filter_rowset(self, obj):
        """
        FilterRowset is very similar to indexed rowlists, but with few facilities
        on top of that (which we don't really need), and with data dictionary with
        stored in 'items' attribute, rather than on object itself.
        """
        return self._pythonize_indexed_lists(obj.items)

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
        CFilterRowsets and IndexedRowLists are dictionary, where keys are some
        indices and values are lists of rows. We assume we do not need keys,
        thus everything is converted into single tuple.
        """
        # Chain all sublists into single list and pass it
        # to regular iterable processor
        return self._pythonize_iterable(chain(*obj.values()))

    def _pythonize_index_rowset(self, obj):
        """
        IndexRowset has iterable with data accessed via 'lines' attribute.
        """
        return self._pythonize_iterable(obj.lines)

    def _pythonize_keyval(self, obj):
        """
        KeyVal is a python-like object, where attributes/values are stored
        as object attributes.
        """
        return self._pythonize_map(obj.__dict__)

    def _pythonize_rowdict(self, obj):
        """
        RowDicts are regular dictionaries, where keys are some IDs and
        values are DBRows. Keys are usually duplicated in rows themselves,
        thus we remove them and compose single list.
        """
        return self._pythonize_iterable(obj.values())

    def _primitive(self, obj):
        return obj

    _conversion_map = {
        'blue.DBRow': _pythonize_dbrow,
        'dbutil.CRowset': _pythonize_iterable,
        'dbutil.CFilterRowset': _pythonize_indexed_lists,
        'dbutil.CIndexedRowset': _pythonize_c_indexed_rowset,
        'dbutil.RowDict': _pythonize_rowdict,
        'dbutil.RowList': _pythonize_iterable,
        '_FixedSizeList': _pythonize_iterable,
        'FSD_Dict': _pythonize_map,
        'FSD_MultiIndex': _pythonize_map,
        'FSD_NamedVector': _pythonize_fsd_named_vector,
        'FSD_Object': _pythonize_fsd_object,
        'util.FilterRowset': _pythonize_filter_rowset,
        'util.IndexedRowLists': _pythonize_indexed_lists,
        'util.IndexRowset': _pythonize_index_rowset,
        'util.KeyVal': _pythonize_keyval,
        'bool': _primitive,
        'dict': _pythonize_map,
        'float': _primitive,
        'int': _primitive,
        'list': _pythonize_iterable,
        'long': _primitive,
        'NoneType': _primitive,
        'str': _primitive,
        'tuple': _pythonize_iterable,
        'unicode': _primitive,
        'universe.SolarSystemWrapper': _pythonize_keyval
    }
