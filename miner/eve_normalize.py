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
        obj_type = getattr(obj, '__guid__', obj.__class__.__name__)
        method = self._conversion_map[obj_type]
        return method(self, obj)

    def _pythonize_dbrow(self, obj):
        """
        DBRow is similar to python dictionary, but its keys are
        accessed in different way.
        """
        container = {}
        for key in obj.__header__.Keys():
            value = obj[key]
            container[key] = self._route_object(value)
        return container

    def _pythonize_crowset(self, obj):
        """
        CRowset for our needs behaves like regular list, only its
        contents are hidden under 'lines' attribute.
        """
        container = []
        for element in obj.lines:
            container.append(self._route_object(element))
        return container

    def _primitive(self, obj):
        return obj

    _conversion_map = {
        'blue.DBRow': _pythonize_dbrow,
        'dbutil.CRowset': _pythonize_crowset,
        'util.IndexRowset': _pythonize_crowset,
        'int': _primitive,
        'unicode': _primitive
    }
