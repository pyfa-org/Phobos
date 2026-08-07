import sqlite3

from util import cachedproperty
from .base import BaseMiner, DiscoveredData, DiscoveryError


class SqliteMiner(BaseMiner):
    """Extract data from SQLite databases bundled with client."""

    name = 'sqlite'

    def __init__(self, resbrowser, translator):
        # Format: {db alias: db path}
        self._resbrowser = resbrowser
        self._translator = translator

    def discovery_error_iter(self):
        for discovery_error in self._contname_dbtable_map.errors:
            yield discovery_error

    def contname_iter(self):
        for container_name in sorted(self._contname_dbtable_map.data):
            yield container_name

    def get_data(self, container_name, language=None, verbose=False, **kwargs):
        try:
            dbpath, table_name = self._contname_dbtable_map.data[container_name]
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
        Format: DiscoveredData(data={container name: (db alias, table name)})
        """
        sqlite_ext = '.db'
        contname_dbtable_map = DiscoveredData(data={})
        for resource_path in self._resbrowser.respath_iter():
            if not resource_path.endswith(sqlite_ext):
                continue
            resource_info = self._resbrowser.get_file_info(resource_path, verify_content=True)
            try:
                table_names = self.__get_table_names(resource_info.file_abspath)
            except (KeyboardInterrupt, SystemExit):
                raise
            # Per-database error logging
            except Exception as e:
                msg = u'unable to read database {} - {}: {}'.format(resource_path, type(e).__name__, e)
                contname_dbtable_map.errors.append(DiscoveryError(msg))
                continue
            for table_name in table_names:
                container_name = u'{}_{}'.format(resource_path[:-len(sqlite_ext)], table_name)
                contname_dbtable_map.data[container_name] = (resource_info.file_abspath, table_name)
        return contname_dbtable_map

    def __get_table_names(self, file_path):
        with sqlite3.connect(file_path) as dbconn:
            c = dbconn.cursor()
            c.execute('select name from sqlite_master where type = \'table\'')
            return [row[0] for row in c]
