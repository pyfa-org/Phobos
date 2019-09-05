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


import pickle

from miner.base import BaseMiner
from util import CachedProperty
from .resbrowser import ResourceBrowser


class ResourcePickleMiner(BaseMiner):
    """
    Class, which attempts to get data from resource
    pickles (this is not guaranteed to succeed).
    """

    name = 'resource_pickle'

    def __init__(self, rvr):
        self._resbrowser = ResourceBrowser(rvr)

    def contname_iter(self):
        for container_name in sorted(self._contname_respath_map):
            yield container_name

    def get_data(self, container_name, **kwargs):
        try:
            resfilepath = self._contname_respath_map[container_name]
        except KeyError:
            self._container_not_found(container_name)
        else:
            resfiledata = self._resbrowser.get_file(resfilepath)
            data = pickle.loads(resfiledata)
            return data

    @CachedProperty
    def _contname_respath_map(self):
        """
        Map between container names and resource path names to pickle files.
        Format: {container name: resource path to pickle}
        """
        pickle_ext = '.pickle'
        contname_respath_map = {}
        for resource_path in self._resbrowser.get_filelist():
            # We also strip .pickle extension from names
            if not resource_path.endswith(pickle_ext):
                continue
            container_name = resource_path[:-len(pickle_ext)]
            contname_respath_map[container_name] = resource_path
        return contname_respath_map
