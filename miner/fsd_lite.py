import json
import re
import sqlite3

from util import cachedproperty
from .base import BaseMiner
from .shared import has_sqlite_header


class FsdLiteMiner(BaseMiner):
    """Class, which fetches data from FSDLite format static cache files."""

    name = 'fsd_lite'

    def __init__(self, resbrowser, translator):
        self._resbrowser = resbrowser
        self._translator = translator

    def contname_iter(self):
        for container_name in sorted(self._contname_respath_map):
            yield container_name

    def get_data(self, container_name, language=None, verbose=False, **kwargs):
        try:
            resource_path = self._contname_respath_map[container_name]
        except KeyError:
            self._container_not_found(container_name)
        else:
            rows = {}
            file_path = self._resbrowser.get_file_info(resource_path, verify_content=True).file_abspath
            with sqlite3.connect(file_path) as dbconn:
                c = dbconn.cursor()
                c.execute(u'select key, value from cache')
                for sqlite_row in c:
                    key = sqlite_row[0]
                    value = sqlite_row[1]
                    row = json.loads(value)
                    rows[key] = row
            self._translator.translate_container(rows, language, verbose=verbose)
            return rows

    @cachedproperty
    def _contname_respath_map(self):
        """
        Map between container names and resource path names to static cache files.
        Format: {container path: resource path to static cache}
        """
        contname_respath_map = {}
        for resource_path in self._resbrowser.respath_iter():
            # Filter by resource file path first
            container_name = self.__get_container_name(resource_path)
            if container_name is None:
                continue
            # Now, check if it's actually sqlite database
            if not self.__check_sqlite(resource_path):
                continue
            contname_respath_map[container_name] = resource_path
        return contname_respath_map

    def __get_container_name(self, resource_path):
        """
        Validate resource path and return stripped resource
        name if path is valid, return None otherwise.
        """
        m = re.match(r'^res:/staticdata/(?P<fname>.+).static$', resource_path)
        if not m:
            return None
        return m.group('fname')

    def __check_sqlite(self, resource_path):
        """Check if file is actually SQLite database."""
        # The check used to connect to DB and check if it has a cache table, but this is not needed
        # to see if file is FSD Lite or FSD Binary
        file_path = self._resbrowser.get_file_info(resource_path, verify_content=False).file_abspath
        try:
            return has_sqlite_header(file_path)
        except KeyboardInterrupt:
            raise
        except:
            return False
