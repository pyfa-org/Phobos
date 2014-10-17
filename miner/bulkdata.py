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


from util import CachedProperty
from .abstract_miner import AbstractMiner
from .eve_normalize import EveNormalizer


class BulkdataMiner(AbstractMiner):
    """
    Class, responsible for fetching data out of bulkdata, which is included
    with EVE client.
    """

    def __init__(self, rvr, translator):
        self._cfg = rvr.getconfigmgr()
        self._translator = translator

    def contname_iter(self):
        for resolved_name in sorted(self._resolved_source_map):
            yield resolved_name

    def get_data(self, resolved_name, language=None, verbose=False, **kwargs):
        try:
            source_name = self._resolved_source_map[resolved_name]
        except KeyError:
            self._container_not_found(resolved_name)
        else:
            container_data = getattr(self._cfg, source_name)
            normalized_data = EveNormalizer().run(container_data)
            self._translator.translate_container(normalized_data, language, stats=verbose)
            return normalized_data

    @CachedProperty
    def _resolved_source_map(self):
        """
        We have to 'secure' container names, thus conflicts are
        possible; resolve them by appending suffix in case we have
        2 or more overlapping 'safe' names, and use this map to
        store relation between resolved name (which is exposed to
        miner users) and source one.
        Format: {resolved name: source name}
        """
        # Intermediate map
        # Format: {safe name: [source names]}
        safe_source_map = {}
        for source_name in self._cfg.tables:
            safe_name = self._secure_name(source_name)
            source_names = safe_source_map.setdefault(safe_name, [])
            source_names.append(source_name)
        # Final map which will be exposed as value of this property
        resolved_source_map = {}
        for safe_name, source_names in safe_source_map.items():
            # Use number suffix with 'miner' marker to resolve conflicts
            if len(source_names) > 1:
                i = 1
                for source_name in sorted(source_names):
                    resolved_name = u'{}_m{}'.format(safe_name, i)
                    resolved_source_map[resolved_name] = source_name
                    i += 1
            # Else, conflict resolution is not needed - just use safe name
            else:
                resolved_source_map[safe_name] = source_names[0]
        return resolved_source_map
