#===============================================================================
# Copyright (C) 2014-2015 Anton Vorobyov
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
import importlib
import inspect
import os
import shutil
import sys
import tempfile

from .abstract_miner import AbstractMiner


@contextlib.contextmanager
def tempdir(prefix='tmp'):
    """A context manager for creating and then deleting a temporary directory."""
    tmpdir = tempfile.mkdtemp(prefix=prefix)
    try:
        yield tmpdir
    finally:
        # this doesn't actually work because the module is loaded within this pyfa process, and cannot be removed . Hence ignore errors
        shutil.rmtree(tmpdir, ignore_errors=True)


class FsdBinaryMiner(AbstractMiner):

    def __init__(self, rvr, translator):
        self._fsd_spec = {
            'dynamicattributes': ('app:/bin64/dynamicItemAttributesLoader.pyd', 'res:/staticdata/dynamicitemattributes.fsdbinary'),
            'iconIDs': ('app:/bin64/iconIDsLoader.pyd', 'res:/staticdata/iconids.fsdbinary'),
            'marketGroups': ('app:/bin64/marketGroupsLoader.pyd', 'res:/staticdata/marketgroups.fsdbinary'),
            'metaGroups': ('app:/bin64/metaGroupsLoader.pyd', 'res:/staticdata/metagroups.fsdbinary')}
        self._rvr = rvr
        self._translator = translator
        eve_path = os.path.join(rvr.paths.sharedcache, 'index_{}.txt'.format(os.path.basename(rvr.paths.root)))
        with open(eve_path, 'r') as f:
            lines = f.readlines()
            self.client_index = {x.split(',')[0]: x.split(',') for x in lines}

    def contname_iter(self):
        for resolved_name in sorted(self._fsd_spec):
            yield resolved_name

    def get_data(self, resolved_name, language=None, verbose=False, **kwargs):
        try:
            loader_location, resource_location = self._fsd_spec[resolved_name]
        except KeyError:
            self._container_not_found(resolved_name)
        else:
            res_cache_path = os.path.join(self._rvr.paths.sharedcache, "ResFiles")
            loader_filename = os.path.split(loader_location)[1]
            loader_relpath = self.client_index[loader_location][1]
            loader_fullpath = os.path.join(res_cache_path, loader_relpath)
            resource_filename = os.path.split(resource_location)[1]
            resource_relpath = self._rvr.rescache._index[resource_location][1]
            resource_fullpath = os.path.join(res_cache_path, resource_relpath)

            with tempdir('phobos-') as temp_dir:
                cwd = os.getcwd()
                sys.path.insert(0, temp_dir)
                os.chdir(temp_dir)

                loader_dest = os.path.join(os.getcwd(), loader_filename)
                shutil.copyfile(loader_fullpath, loader_dest)
                resource_dest = os.path.join(os.getcwd(), resource_filename)
                shutil.copyfile(resource_fullpath, resource_dest)

                loader_modname = os.path.splitext(loader_filename)[0]
                loader_module = importlib.import_module(loader_modname)
                fsd_data = loader_module.load(resource_dest)

                os.chdir(cwd)
                sys.path.remove(temp_dir)

            def normalize_list(data):
                l = [normalize_object(v) for v in data]
                return l

            def normalize_dict(data):
                d = {}
                for k, v in data.items():
                    d[normalize_object(k)] = normalize_object(v)
                return d

            def normalize_fsd_item(data):
                item = {}
                for attr_name in dir(data):
                    if attr_name.startswith('__') and attr_name.endswith('__'):
                        continue
                    item[attr_name] = normalize_object(getattr(data, attr_name))
                return item

            class_map = {
                'dict': normalize_dict,
                'list': normalize_list}
            primitives = (int, float, str, unicode, bool, type(None))

            def normalize_object(obj):
                if isinstance(obj, primitives):
                    return obj
                type_name = type(obj).__name__
                if type_name in class_map:
                    converter = class_map[type_name]
                    return converter(obj)
                if inspect.getmodule(type(obj)) is loader_module:
                    return normalize_fsd_item(obj)
                print('unable to convert object from fsdbinary format', obj)

            normalized_data = normalize_object(fsd_data)
            self._translator.translate_container(normalized_data, language, verbose=verbose)
            return normalized_data
