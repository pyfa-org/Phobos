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


import sqlite3

from util import cachedproperty
from .base import BaseMiner


class SqliteMiner(BaseMiner):
    """
    Extract data from SQLite databases bundled with client.
    """

    name = 'sqlite'

    def __init__(self, resbrowser, translator):
        # Format: {db alias: db path}
        self._resbrowser = resbrowser
        self._translator = translator

    def contname_iter(self):
        for container_name in sorted(self._contname_dbtable_map):
            yield container_name

    def get_data(self, container_name, language=None, verbose=False, **kwargs):
        try:
            dbpath, table_name = self._contname_dbtable_map[container_name]
        except KeyError:
            self._container_not_found(container_name)
        else:
            rows = []
            with sqlite3.connect(dbpath) as dbconn:
                c = dbconn.cursor()
                c.execute(u'select * from {}'.format(table_name))
                headers = list(map(lambda x: x[0], c.description))
                for sqlite_row in c:
                    row = dict(zip(headers, sqlite_row))
                    rows.append(row)
            self._translator.translate_container(rows, language, verbose=verbose)
            return rows

    @cachedproperty
    def _contname_dbtable_map(self):
        """
        Map between container names and DB tables where data is stored.
        Format: {container name: (db alias, table name)}
        """
        sqlite_ext = '.db'
        contname_dbtable_map = {}
        for resource_path in self._resbrowser.respath_iter():
            if not resource_path.endswith(sqlite_ext):
                continue
            resource_info = self._resbrowser.get_file_info(resource_path)
            with sqlite3.connect(resource_info.file_abspath) as dbconn:
                c = dbconn.cursor()
                c.execute('select name from sqlite_master where type = \'table\'')
                for row in c:
                    table_name = row[0]
                    container_name = u'{}_{}'.format(resource_path[:-len(sqlite_ext)], table_name)
                    contname_dbtable_map[container_name] = (resource_info.file_abspath, table_name)
        return contname_dbtable_map
