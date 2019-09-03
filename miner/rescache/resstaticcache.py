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


import json
import os
import re
import sqlite3

from miner.base import BaseMiner
from util import CachedProperty
from .resbrowser import ResourceBrowser


class ResourceStaticCacheMiner(BaseMiner):
    """
    Class, which fetches data from FSDLite format
    static cache files.
    """

    def __init__(self, rvr, translator):
        self._rvr = rvr
        self._resbrowser = ResourceBrowser(rvr)
        self._translator = translator

    def contname_iter(self):
        for resolved_name in sorted(self._resolved_source_map):
            yield resolved_name

    def get_data(self, resolved_name, language=None, verbose=False, **kwargs):
        try:
            resfilepath = self._resolved_source_map[resolved_name]
        except KeyError:
            self._container_not_found(resolved_name)
        else:
            fs_path = self.__get_filesystem_path(resfilepath)
            dbconn = sqlite3.connect(fs_path)
            c = dbconn.cursor()
            rows = {}
            c.execute(u'select key, value from cache')
            for sqlite_row in c:
                key = sqlite_row[0]
                value = sqlite_row[1]
                row = json.loads(value)
                rows[key] = row
            self._translator.translate_container(rows, language, verbose=verbose)
            return rows

    @CachedProperty
    def _resolved_source_map(self):
        """
        Map between secure conflict-free paths w/o extensions
        and original full resource paths.
        Format: {resolved path: path to pickle}
        """
        # Format: {safe path: [source paths]}
        safe_source_map = {}
        for source_path in self._resbrowser.get_filelist():
            # Filter by resource file path first
            source_name = self.__get_source_name(source_path)
            if source_name is None:
                continue
            # Now, check if it's actually sqlite database and if it has cache table
            if not self.__check_cache(source_path):
                continue
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

    def __get_source_name(self, source_path):
        """
        Validate source path and return stripped source
        name if path is valid, return None instead.
        """
        m = re.match(r'^res:/staticdata/(?P<fname>.+).static$', source_path)
        if not m:
            return None
        return m.group('fname')

    def __check_cache(self, source_path):
        """
        Check if file is actually SQLite database and has
        cache table.
        """
        fs_path = self.__get_filesystem_path(source_path)
        try:
            dbconn = sqlite3.connect(fs_path)
            c = dbconn.cursor()
            c.execute('select count(*) from sqlite_master where type = \'table\' and name = \'cache\'')
        except KeyboardInterrupt:
            raise
        except:
            has_cache = False
        else:
            has_cache = False
            for row in c:
                has_cache = bool(row[0])
        return has_cache

    def __get_filesystem_path(self, source_path):
        rc = self._rvr.rescache
        return os.path.join(rc._sharedCachePath, 'ResFiles', rc._index[source_path][1])
