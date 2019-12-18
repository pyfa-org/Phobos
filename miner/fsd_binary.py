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


import contextlib
import gc
import importlib
import os
import re
import shutil
import struct
import sys
import tempfile

from util import EveNormalizer, cachedproperty
from .base import BaseMiner


class FsdBinaryMiner(BaseMiner):

    name = 'fsd_binary'

    def __init__(self, resbrowser, translator):
        self._resbrowser = resbrowser
        self._translator = translator
        self.__temp_dir = None

    def contname_iter(self):
        for container_name in sorted(self._contname_fsdfiles_map):
            yield container_name

    def get_data(self, container_name, language=None, verbose=False, **kwargs):
        try:
            loader_respath, data_respath = self._contname_fsdfiles_map[container_name]
        except KeyError:
            self._container_not_found(container_name)
        else:
            if os.name != 'nt' or struct.calcsize('P') * 8 != 64:
                msg = 'need 64-bit python under Windows to execute loader'
                raise PlatformError(msg)
            loader_filename = loader_respath.split('/')[-1]
            loader_info = self._resbrowser.get_file_info(loader_respath)
            data_info = self._resbrowser.get_file_info(data_respath)

            with self._temp_dir() as temp_dir:
                sys.path.insert(0, temp_dir)

                loader_dest = os.path.join(temp_dir, loader_filename)
                if not os.path.isfile(loader_dest) or not self._compare_files(loader_info.file_abspath, loader_dest):
                    shutil.copyfile(loader_info.file_abspath, loader_dest)

                loader_modname = os.path.splitext(loader_filename)[0]
                loader_module = importlib.import_module(loader_modname)
                fsd_data = loader_module.load(data_info.file_abspath)
                normalized_data = EveNormalizer().run(fsd_data, loader_module=loader_module)

                sys.path.remove(temp_dir)
                del loader_module
                del sys.modules[loader_modname]
                gc.collect()

            self._translator.translate_container(normalized_data, language, verbose=verbose)
            return normalized_data

    @cachedproperty
    def _contname_fsdfiles_map(self):
        """
        Map between container names and locations of FSD loader/data.
        Format: {container name: (fsd loader file path, fsd data file path)}
        """
        loaders = {}
        datas = {}
        for resource_path in self._resbrowser.respath_iter():
            m = re.match('^app:/bin64/(\w+/)*(?P<name>\w+)Loader.pyd$', resource_path, flags=re.UNICODE)
            if m:
                loaders[m.group('name').lower()] = resource_path
                continue
            m = re.match('^res:/staticdata/(\w+/)*(?P<name>\w+).fsdbinary$', resource_path, flags=re.UNICODE)
            if m:
                datas[m.group('name').lower()] = resource_path
                continue
        contname_fsdfiles_map = {}
        for container_name in set(loaders).intersection(datas):
            contname_fsdfiles_map[container_name] = (loaders[container_name], datas[container_name])
        return contname_fsdfiles_map

    @contextlib.contextmanager
    def _temp_dir(self):
        """A context manager for creating and then deleting a temporary directory."""
        if self.__temp_dir is None:
            self.__temp_dir = tempfile.mkdtemp(prefix='phobos-')
        try:
            yield self.__temp_dir
        # Try to remove folder, but be silent if it fails, as it is to be expected, because
        # python process which has used library from this folder is still running
        finally:
            error_data = []

            def on_error(*args, **kwargs):
                error_data.append((args, kwargs))

            shutil.rmtree(self.__temp_dir, ignore_errors=False, onerror=on_error)
            # Avoid creating new dirs in future if we haven't removed this one
            if not error_data:
                self.__temp_dir = None

    def _compare_files(self, file1_path, file2_path):
        with open(file1_path, 'rb') as f1, open(file2_path, 'rb') as f2:
            return f1.read() == f2.read()


class PlatformError(Exception):
    """Raised when FSD binary miner is used on incorrect platform."""
    pass
