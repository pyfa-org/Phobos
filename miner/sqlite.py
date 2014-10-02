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


import os.path
import sqlite3

from util import CachedProperty
from .abstract_miner import AbstractMiner
from .exception import ContainerNameError


class SqliteMiner(AbstractMiner):
    """
    Extract data from SQLite databases bundled with client.
    """

    def __init__(self, path_eve):
        # Format: {db alias: db connection}
        self._databases = {
            'mapbulk': sqlite3.connect(os.path.join(path_eve, 'bulkdata', 'mapbulk.db'))
        }

    def contname_iter(self):
        for resolved_name in sorted(self._resolved_source_map):
            yield resolved_name

    def get_data(self, resolved_name):
        try:
            dbname, table_name = self._resolved_source_map[resolved_name]
        except KeyError:
            msg = u'container "{}" is not available for miner {}'.format(resolved_name, type(self).__name__)
            raise ContainerNameError(msg)
        dbconn = self._databases[dbname]
        c = dbconn.cursor()
        rows = []
        c.execute(u'select * from {}'.format(table_name))
        headers = list(map(lambda x: x[0], c.description))
        for sqlite_row in c:
            row = dict(zip(headers, sqlite_row))
            rows.append(row)
        return rows

    @CachedProperty
    def _resolved_source_map(self):
        """
        Map between secured/conflict-free names and the place where
        data source is located.
        Format: {resolved name: (db alias, table name)}
        """
        # Format: {safe name: [(db alias, table name), ...]}
        safe_source_map = {}
        for dbname, dbconn in self._databases.items():
            c = dbconn.cursor()
            c.execute('select name from sqlite_master where type = \'table\'')
            for row in c:
                table_name = row[0]
                source_name = u'{}_{}'.format(dbname, table_name)
                safe_name = self._secure_name(source_name)
                sources = safe_source_map.setdefault(safe_name, [])
                sources.append((dbname, table_name))
        resolved_source_map = {}
        for safe_name, sources in safe_source_map.items():
            # Use number suffix with 'miner' marker to resolve conflicts
            if len(sources) > 1:
                i = 1
                for source in sorted(sources):
                    resolved_name = u'{}_m{}'.format(safe_name, i)
                    resolved_source_map[resolved_name] = source
                    i += 1
            else:
                resolved_source_map[safe_name] = sources[0]
        return resolved_source_map
