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


from reverence import blue

from .abstract_miner import AbstractMiner
from .eve_normalize import EveNormalizer
from .exception import ContainerNameError


class BulkdataMiner(AbstractMiner):
    """
    Class, responsible for fetching data out of bulkdata, which is included
    with EVE client.
    """

    def __init__(self, path_eve, path_cache, server):
        # Initialize reverence
        eve = blue.EVE(path_eve, cachepath=path_cache, server=server)
        self.cfg = eve.getconfigmgr()
        self.__name_source_map = None

    def contname_iter(self):
        for modified_name in sorted(self._name_source_map):
            yield modified_name

    def get_data(self, modified_name):
        try:
            source_name = self._name_source_map[modified_name]
            container_data = getattr(self.cfg, source_name)
        except (KeyError, AttributeError):
            msg = u'container "{}" is not available for miner {}'.format(modified_name, type(self).__name__)
            raise ContainerNameError(msg)
        normalized_data = EveNormalizer().run(container_data)
        return normalized_data

    @property
    def _name_source_map(self):
        """
        We have to 'secure' container names, thus conflicts are
        possible; resolve them by appending suffix in case we have
        2 or more overlapping 'safe' names, and use this map to
        store relation between modified name (which is exposed to
        miner users) and source one.
        """
        if self.__name_source_map is None:
            # Intermediate map
            # Format: {safe name: [source, names]}
            modified_source_map = {}
            for source_name in sorted(self.cfg.tables):
                safe_name = self._secure_name(source_name)
                source_names = modified_source_map.setdefault(safe_name, [])
                source_names.append(source_name)
            # Format: {modified name: source name}
            self.__name_source_map = {}
            for safe_name, source_names in modified_source_map.items():
                if len(source_names) > 1:
                    for i in range(len(source_names)):
                        source_name = source_names[i]
                        # Use number suffix to resolve conflicts
                        modified_name = u'{}_{}'.format(safe_name, i + 1)
                        self.__name_source_map[modified_name] = source_name
                else:
                    self.__name_source_map[safe_name] = source_names[0]
        return self.__name_source_map
