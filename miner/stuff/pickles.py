#===============================================================================
# Copyright (C) 2014 Anton Vorobyov
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

from miner.abstract_miner import AbstractMiner
from miner.exception import ContainerNameError
from util import CachedProperty
from .unstuff import Unstuffer


class PickleMiner(AbstractMiner):
    """
    Class, which attempts to get data from stuffed
    pickles (this is not guaranteed to succeed).
    """

    def __init__(self, rvr):
        self._unstuffer = Unstuffer(rvr)

    def contname_iter(self):
        for resolved_name in sorted(self._resolved_source_map):
            yield resolved_name

    def get_data(self, resolved_name):
        try:
            resfilepath = self._resolved_source_map[resolved_name]
        except KeyError:
            msg = u'container "{}" is not available for miner {}'.format(resolved_name, type(self).__name__)
            raise ContainerNameError(msg)
        resfiledata = self._unstuffer.get_file(resfilepath)
        data = pickle.loads(resfiledata)
        return data

    @CachedProperty
    def _resolved_source_map(self):
        """
        Map between secure conflict-free paths w/o extensions
        and original full resource paths.
        Format: {resolved path: path to pickle}
        """
        pickle_ext = '.pickle'
        # Format: {safe path: [source paths]}
        safe_source_map = {}
        for source_path in self._unstuffer.get_filelist():
            # We also strip .pickle extension from names
            if not source_path.endswith(pickle_ext):
                continue
            source_name = source_path[:-len(pickle_ext)]
            safe_name = self._secure_name(source_name)
            source_paths = safe_source_map.setdefault(safe_name, [])
            source_paths.append(source_path)
        resolved_source_map = {}
        for safe_name, source_paths in safe_source_map.items():
            # Use number suffix with 'miner' marker to resolve conflicts
            if len(source_paths) > 1:
                i = 1
                for source_path in sorted(source_paths):
                    resolved_name = u'{}_m{}'.format(safe_name, i)
                    resolved_source_map[resolved_name] = source_path
                    i += 1
            else:
                resolved_source_map[safe_name] = source_paths[0]
        return resolved_source_map
