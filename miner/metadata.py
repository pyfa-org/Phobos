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
from ConfigParser import ConfigParser
from datetime import datetime
from time import mktime

from .abstract_miner import AbstractMiner
from .exception import TableNameError


class MetadataMiner(AbstractMiner):
    """
    Provide some metadata on when this data dump has been made
    and which data source has been used for that.
    """

    def __init__(self, path_eve):
        self._table_name = 'metadata'
        self.path_eve = path_eve

    def tablename_iter(self):
        for table_name in (self._table_name,):
            yield table_name

    def get_table(self, table_name):
        if table_name != self._table_name:
            msg = u'table "{}" is not available for miner {}'.format(table_name, type(self).__name__)
            raise TableNameError(msg)
        field_names = ('field_name', 'field_value')
        lines = []
        # Read client version
        try:
            config = ConfigParser()
            config.read(os.path.join(self.path_eve, 'start.ini'))
            eve_version = config.getint('main', 'build')
        except KeyboardInterrupt:
            raise
        except:
            print(u'    failed to detect client version')
            eve_version = None
        lines.append({field_names[0]: 'client_build', field_names[1]: eve_version})
        # Generate UNIX-style timestamp of current UTC time
        timestamp = int(mktime(datetime.utcnow().timetuple()))
        lines.append({field_names[0]: 'dump_time', field_names[1]: timestamp})
        return tuple(lines)
