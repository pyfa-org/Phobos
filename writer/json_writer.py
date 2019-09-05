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


import json
import os.path
import re
import types

from .base import BaseWriter


class CustomEncoder(json.JSONEncoder):
    """
    If we're not happy with default encoder - all modifications
    are implemented in this class.
    """

    def encode(self, obj, *args, **kwargs):
        if isinstance(obj, dict):
            self._map_keys_to_str(obj)
        return json.JSONEncoder.encode(self, obj, *args, **kwargs)

    def iterencode(self, obj, *args, **kwargs):
        # Traverse passed object, and do some modifications
        self._route_object(obj)
        # Pass it to usual encoder
        return json.JSONEncoder.iterencode(self, obj, *args, **kwargs)

    def _route_object(self, obj):
        obj_type = type(obj)
        method = self._traversal_map.get(obj_type)
        if method is not None:
            method(self, obj)

    def _traverse_map(self, obj):
        """
        Traverse through dict items first, then convert
        keys to strings.
        """
        for k, v in obj.items():
            self._route_object(k)
            self._route_object(v)
        self._map_keys_to_str(obj)

    def _traverse_iterable(self, obj):
        for item in obj:
            self._route_object(item)

    _traversal_map = {
        types.DictType: _traverse_map,
        types.TupleType: _traverse_iterable,
        types.ListType: _traverse_iterable
    }

    def _map_keys_to_str(self, obj):
        """
        Unconditionally convert dictionary keys to
        strings. Default encoder doesn't do this for
        cases when keys are python objects like tuple,
        and encoding fails.
        """
        new_dict = {}
        for k, v in obj.items():
            new_dict[unicode(k)] = v
        obj.clear()
        obj.update(new_dict)


class JsonWriter(BaseWriter):
    """
    Class, which stores fetched data on storage device
    as JSON files.
    """

    def __init__(self, folder, indent=None):
        self.base_folder = folder
        self.indent = indent

    def write(self, miner_name, container_name, container_data):
        # Create folder structure to path, if not created yet
        folder = os.path.join(self.base_folder, self.__secure_name(miner_name))
        if not os.path.exists(folder):
            os.makedirs(folder, mode=0o755)
        data_str = json.dumps(
            container_data,
            ensure_ascii=False,
            cls=CustomEncoder,
            indent=self.indent)
        data_bytes = data_str.encode('utf8')
        filepath = os.path.join(folder, '{}.json'.format(self.__secure_name(container_name)))
        with open(filepath, 'wb') as f:
            f.write(data_bytes)

    def __secure_name(self, name):
        """
        As we're writing to disk, we should get rid of all
        filesystem-specific symbols.
        """
        # Prefer safe way - replace any characters besides
        # alphanumeric and few special characters with
        # underscore
        writer_safe_name = re.sub('[^\w\-.,() ]', '_', name, flags=re.UNICODE)
        return writer_safe_name
