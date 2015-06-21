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
import glob
import os.path
import sqlite3

from util import CachedProperty
from .abstract_miner import AbstractMiner


class StaticdataCacheMiner(AbstractMiner):
    """
    Some of cache tables are stored in FSDLite (SQLite + JSON)
    format. We simplify it into plain dict of keyed data rows.,
    """

    def __init__(self, path_eve, translator):
        self._dbext = '.db'
        self._path_staticdata = os.path.join(path_eve, 'bin', 'staticdata')
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
            file_name = '{}{}'.format(source_name, self._dbext)
            file_path = os.path.join(self._path_staticdata, file_name)
            dbconn = sqlite3.connect(file_path)
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
        Map between secured/conflict-free names and the place where
        data source is located.
        Format: {resolved name: source file name}
        """
        # Format: {safe name: [raw names]}
        safe_source_map = {}
        for file_path in glob.glob(os.path.join(self._path_staticdata, '*{}'.format(self._dbext))):
            if not os.path.isfile(file_path):
                continue
            # Check if there's cache table, and skip files w/o it
            dbconn = sqlite3.connect(file_path)
            c = dbconn.cursor()
            c.execute('select count(*) from sqlite_master where type = \'table\' and name = \'cache\'')
            has_cache = False
            for row in c:
                has_cache = bool(row[0])
            if not has_cache:
                continue
            file_name = os.path.split(file_path)[1]
            source_name = os.path.splitext(file_name)[0]
            safe_name = self._secure_name(source_name)
            sources = safe_source_map.setdefault(safe_name, [])
            sources.append(source_name)
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
