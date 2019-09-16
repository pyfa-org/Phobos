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


import csv
import hashlib
import os
from collections import namedtuple

from util import cachedproperty


FileInfo = namedtuple('FileInfo', ('resource_path', 'file_relpath', 'file_abspath', 'file_hash', 'file_size', 'compressed_size'))


class ResourceBrowser(object):
    """
    Class, responsible for browsing/retrieval of resources.
    """

    def __init__(self, eve_path, server_alias):
        self._eve_path = eve_path
        self._server_alias = server_alias

    def respath_iter(self):
        """
        Aggregate filepaths from all resource files and return
        them in the form of single list.
        """
        for resource_path in self._resource_index:
            yield resource_path

    def get_file_data(self, resource_path):
        """Return file contents for requested resource."""
        file_info = self._resource_index[resource_path]
        file_path = file_info.file_abspath
        with open(file_path, 'rb') as f:
            data = f.read()
        self.__verify_data(data=data, file_info=file_info)
        return data

    def get_file_info(self, resource_path):
        """Return file info for requested resource."""
        file_info = self._resource_index[resource_path]
        file_path = file_info.file_abspath
        with open(file_path, 'rb') as f:
            data = f.read()
        self.__verify_data(data=data, file_info=file_info)
        return file_info

    def __verify_data(self, data, file_info):
        if len(data) != file_info.file_size:
            raise FileIntegrityError(u'file size mismatch when reading {}'.format(file_info.resource_path))
        m = hashlib.md5()
        m.update(data)
        if m.hexdigest() != file_info.file_hash:
            raise FileIntegrityError(u'file hash mismatch when reading {}'.format(file_info.resource_path))

    @cachedproperty
    def _resource_index(self):
        index = {}
        res_index_path = os.path.join(self._eve_path, 'SharedCache', self._server_alias, 'resfileindex.txt')
        with open(res_index_path) as f:
            for resource_path, file_relpath, file_hash, file_size, compressed_size in csv.reader(f):
                index[resource_path] = FileInfo(
                    resource_path=resource_path,
                    file_relpath=os.path.join(*file_relpath.split('/')),
                    file_abspath=os.path.join(self._eve_path, 'SharedCache', 'ResFiles', *file_relpath.split('/')),
                    file_hash=file_hash,
                    file_size=int(file_size),
                    compressed_size=int(compressed_size))
        app_index_path = os.path.join(self._eve_path, 'SharedCache', u'index_{}.txt'.format(self._server_alias))
        with open(app_index_path) as f:
            for resource_path, file_relpath, file_hash, file_size, compressed_size, version in csv.reader(f):
                index[resource_path] = FileInfo(
                    resource_path=resource_path,
                    file_relpath=os.path.join(*file_relpath.split('/')),
                    file_abspath=os.path.join(self._eve_path, 'SharedCache', 'ResFiles', *file_relpath.split('/')),
                    file_hash=file_hash,
                    file_size=int(file_size),
                    compressed_size=int(compressed_size))
        return index


class FileIntegrityError(Exception):
    pass
