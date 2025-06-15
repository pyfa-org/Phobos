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
import typing
from collections import OrderedDict, abc
from itertools import chain


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
            try:
                parent_match = isinstance(obj, candidate_cls)
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                continue
            else:
                if parent_match:
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

    def _pythonize_pyobj(self, obj):
        """
        KeyVal is a python-like object, where attributes/values are stored
        as object attributes.
        """
        return self._pythonize_map(obj.__dict__)

    def pythonize_fsdbinary_item(self, obj, ignore_attrs=()):
        item = {}
        for attr_name in dir(obj):
            if attr_name.startswith('__') and attr_name.endswith('__'):
                continue
            if attr_name in ignore_attrs:
                continue
            sub_obj = getattr(obj, attr_name)
            if isinstance(sub_obj, typing.Callable):
                continue
            item[attr_name] = self._route_object(sub_obj)
        return item

    _primitives = (
        types.NoneType,
        bool,
        float,
        int,
        str)

    _class_match = {
        list: _pythonize_iterable,
        tuple: _pythonize_iterable}

    _name_match = {
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
        'universe.SolarSystemWrapper': _pythonize_pyobj}

    _subclass_match = OrderedDict([
        # Includes dictionaries and FSDLiteStorage
        (abc.Mapping, _pythonize_map)])


class UnknownContainerTypeError(Exception):
    """
    Raised when normalizer doesn't know what to do
    with passed object.
    """
    pass
