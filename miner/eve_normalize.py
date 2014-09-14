#===============================================================================
# Copyright (C) 2012 Diego Duclos
# Copyright (C) 2013-2014 Anton Vorobyov
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
        try:
            obj_type = getattr(obj, '__guid__', type(obj).__name__)
        # Work around for reverence issue #23
        except TypeError:
            obj_type = obj.__class__.__name__
        method = self._conversion_map[obj_type]
        return method(self, obj)

    def _pythonize_list(self, obj):
        """
        For objects which have access interface similar to
        python lists, but actually have different class.
        """
        return tuple(self._route_object(i) for i in obj)

    def _pythonize_dict(self, obj):
        """
        For objects which have access interface similar to
        python dictionaries, but actually have different class.
        """
        container = {}
        for key, value in obj.iteritems():
            proc_key = self._route_object(key)
            proc_value = self._route_object(value)
            container[proc_key] = proc_value
        return container

    def _pythonize_crowset(self, obj):
        """
        CRowset for our needs behaves like regular list, only its
        contents are hidden under 'lines' attribute.
        """
        return tuple(self._route_object(i) for i in obj.lines)

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

    def _pythonize_filterrowset(self, obj):
        """
        FilterRowset is very similar to indexed rowlists, but with few facilities
        on top of that (whoch we don't really need) and dictionary with data is stored
        in 'items' attribute, rather than on object itself.
        """
        return self._pythonize_indexed_rowlists(obj.items)

    def _pythonize_indexed_rowlists(self, obj):
        """
        Indexed row list is dictionary, where keys are some indexes and
        values are lists of rows. We assume we do not need keys, thus everything
        is converted into single list.
        """
        container = []
        for sublist in obj.values():
            for row in sublist:
                container.append(self._route_object(row))
        return tuple(container)

    def _pythonize_fsdobj(self, obj):
        """
        FSD object is similar to python dictionary, but its keys are
        accessed via 'attributes' attribute.
        """
        container = {}
        for key in obj.attributes:
            # Sometimes values are missing
            value = getattr(obj, key, None)
            proc_key = self._route_object(key)
            proc_value = self._route_object(value)
            container[proc_key] = proc_value
        return container

    def _pythonize_fsdnamedvector(self, obj):
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

    def _primitive(self, obj):
        return obj

    _conversion_map = {
        'blue.DBRow': _pythonize_dbrow,
        'dbutil.CRowset': _pythonize_crowset,
        '_FixedSizeList': _pythonize_list,
        'FSD_Dict': _pythonize_dict,
        'FSD_MultiIndex': _pythonize_dict,
        'FSD_NamedVector': _pythonize_fsdnamedvector,
        'FSD_Object': _pythonize_fsdobj,
        'util.FilterRowset': _pythonize_filterrowset,
        'util.IndexedRowLists': _pythonize_indexed_rowlists,
        'util.IndexRowset': _pythonize_crowset,
        'bool': _primitive,
        'dict': _pythonize_dict,
        'float': _primitive,
        'int': _primitive,
        'list': _pythonize_list,
        'long': _primitive,
        'NoneType': _primitive,
        'str': _primitive,
        'tuple': _pythonize_list,
        'unicode': _primitive
    }
