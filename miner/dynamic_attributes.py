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


import re
import contextlib
import tempfile
import shutil
import sys
import os

from .abstract_miner import AbstractMiner

LOADER_FILE = 'app:/bin/dynamicItemAttributesLoader.pyd'
RES_FILE = 'res:/staticdata/dynamicitemattributes.fsdbinary'


@contextlib.contextmanager
def tempdir(prefix='tmp'):
    """A context manager for creating and then deleting a temporary directory."""
    tmpdir = tempfile.mkdtemp(prefix=prefix)
    try:
        yield tmpdir
    finally:
        # this doesn't actually work because the module is loaded within this pyfa process, and cannot be removed . Hence ignore errors
        shutil.rmtree(tmpdir, ignore_errors=True)


class DynamicAttributesMiner(AbstractMiner):
    def __init__(self, rvr):
        self._container_name = self._secure_name('dynamicattributes')
        self._rvr = rvr
        self.binary_file = os.path.split(RES_FILE)[1]
        eve_path = os.path.join(rvr.paths.sharedcache, 'index_{}.txt'.format(os.path.basename(rvr.paths.root)))
        with open(eve_path, 'r') as f:
            lines = f.readlines()
            self.file_index = {x.split(',')[0]: x.split(',') for x in lines}

    def contname_iter(self):
        for resolved_name in (self._container_name,):
            yield resolved_name

    def get_data(self, resolved_name, language='en-us', **kwargs):
        cwd = os.getcwd()

        with tempdir('pyhobos-') as temp_dir:
            os.chdir(temp_dir)
            sys.path.append(temp_dir)
            res_cache = os.path.join(self._rvr.paths.sharedcache, "ResFiles")

            # Need to copy the file to  our cuirrent directory
            attribute_loader_file = os.path.join(res_cache, self.file_index[LOADER_FILE][1])
            dst = os.path.join(os.getcwd(), os.path.split(LOADER_FILE)[1])
            shutil.copyfile(attribute_loader_file, dst)

            # The loader expect it to be the correct filename, so copy trhe file as well
            dynattribute_file = os.path.join(res_cache, self._rvr.rescache._index[RES_FILE.lower()][1])
            dst = os.path.join(os.getcwd(), self.binary_file)
            shutil.copyfile(dynattribute_file, dst)

            import dynamicItemAttributesLoader

            binary = os.path.join(temp_dir, self.binary_file)
            attributes = dynamicItemAttributesLoader.load(binary)
            os.chdir(cwd)

        attributes_obj = {}

        # convert top level to dict
        attributes = dict(attributes)

        # This is such a brute force method. todo: recursively generate this by inspecting the objects
        for k, v in attributes.items():
            attributes_obj[k] = {
                'attributeIDs': dict(v.attributeIDs),
                'inputOutputMapping': list(v.inputOutputMapping)
            }

            for i, x in enumerate(v.inputOutputMapping):
                attributes_obj[k]['inputOutputMapping'][i] = {
                    'resultingType': x.resultingType,
                    'applicableTypes': list(x.applicableTypes)
                }

            for k2, v2 in v.attributeIDs.items():
                attributes_obj[k]['attributeIDs'][k2] = {
                    'min': v2.min,
                    'max': v2.max
                }
        return attributes_obj

