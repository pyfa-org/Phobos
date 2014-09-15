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
        self.__original_name_map = None

    @property
    def _original_name_map(self):
        """
        We have to 'secure' table names, thus conflicts are possible;
        resolve them by appending suffix in case we have 2 or more
        overlapping 'safe' names, and use this map to store relation
        between final (which is exposed to miner users) name and
        original one.
        """
        if self.__original_name_map is None:
            # Intermediate map
            # Format: {safe name: [original, names]}
            safe_original_map = {}
            for original_name in sorted(self.cfg.tables):
                safe_name = self._secure_name(original_name)
                original_names = safe_original_map.setdefault(safe_name, [])
                original_names.append(original_name)
            # Format: {safe name with suffix: original name}
            self.__original_name_map = {}
            for safe_name, original_names in safe_original_map.items():
                if len(original_names) > 1:
                    for i in range(len(original_names)):
                        original_name = original_names[i]
                        # Use number suffix to resolve conflicts
                        suffixed_safe_name = u'{}_{}'.format(safe_name, i + 1)
                        self.__original_name_map[suffixed_safe_name] = original_name
                else:
                    self.__original_name_map[safe_name] = original_names[0]
        return self.__original_name_map

    def contname_iter(self):
        for container_name in sorted(self._original_name_map):
            yield container_name

    def get_data(self, container_name):
        try:
            original_name = self._original_name_map[container_name]
            container_data = getattr(self.cfg, original_name)
        except (KeyError, AttributeError):
            msg = u'container "{}" is not available for miner {}'.format(container_name, type(self).__name__)
            raise ContainerNameError(msg)
        normalized_data = EveNormalizer().run(container_data)
        return normalized_data
