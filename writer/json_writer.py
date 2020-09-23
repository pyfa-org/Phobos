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
from collections import OrderedDict
from itertools import izip_longest

from .base import BaseWriter


class CustomEncoder(json.JSONEncoder):
    """
    If we're not happy with default encoder - all modifications
    are implemented in this class.
    """

    def encode(self, obj, *args, **kwargs):
        obj = self._route_object(obj)
        return json.JSONEncoder.encode(self, obj, *args, **kwargs)

    def iterencode(self, obj, *args, **kwargs):
        obj = self._route_object(obj)
        return json.JSONEncoder.iterencode(self, obj, *args, **kwargs)

    def _route_object(self, obj):
        obj_type = type(obj)
        method = self._traversal_map.get(obj_type)
        if method is not None:
            new_obj = method(self, obj)
        else:
            new_obj = obj
        return new_obj

    def _traverse_map(self, obj):
        """
        Traverse through dict items first, then convert
        keys to strings.
        """
        new_obj = {}
        for k, v in obj.items():
            new_obj[self._route_object(k)] = self._route_object(v)
        new_obj = self._prepare_map(new_obj)
        return new_obj

    def _traverse_iterable(self, obj):
        new_obj = []
        for item in obj:
            new_obj.append(self._route_object(item))
        return new_obj

    _traversal_map = {
        types.DictType: _traverse_map,
        types.TupleType: _traverse_iterable,
        types.ListType: _traverse_iterable}

    def _prepare_map(self, obj):
        """
        Sort keys the way we want and unconditionally convert dictionary keys
        to strings. Default encoder doesn't do this for cases when keys are
        python objects like tuple, and encoding fails.
        """
        new_obj = OrderedDict()
        for k in sorted(obj.keys(), key=self.__sort_natural):
            new_obj[unicode(k)] = obj[k]
        return new_obj

    def __sort_natural(self, i):
        return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', i)]


class JsonWriter(BaseWriter):
    """
    Class, which stores fetched data on storage device
    as JSON files.
    """

    def __init__(self, folder, indent=None, group=None):
        self.base_folder = folder
        self.indent = indent
        self.group = group

    @staticmethod
    def __grouper(iterable, n, fillvalue=None):
        args = [iter(iterable)] * n
        return izip_longest(fillvalue=fillvalue, *args)

    def write(self, miner_name, container_name, container_data):
        # Create folder structure to path, if not created yet
        folder = os.path.join(self.base_folder, self.__secure_name(miner_name))
        if not os.path.exists(folder):
            os.makedirs(folder, mode=0o755)

        if self.group is None:
            filepath = os.path.join(folder, u'{}.json'.format(self.__secure_name(container_name)))
            self.__write_file(container_data, filepath)
        else:
            for i, group in enumerate(JsonWriter.__grouper(container_data, self.group)):
                filepath = os.path.join(folder, u'{}.{}.json'.format(self.__secure_name(container_name), i))
                if type(container_data) == dict:
                    data = dict((k, container_data[k]) for k in group if k is not None)
                else:
                    data = [k for k in group if k is not None]
                self.__write_file(data, filepath)

    def __write_file(self, data, filepath):
        data_str = json.dumps(
            data,
            ensure_ascii=False,
            cls=CustomEncoder,
            indent=self.indent,
            # We're handling sorting in customized encoder
            sort_keys=False)
        data_bytes = data_str.encode('utf8')
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
