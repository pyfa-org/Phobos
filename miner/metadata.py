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


import os.path
from ConfigParser import ConfigParser
from time import time

from .base import BaseMiner


class MetadataMiner(BaseMiner):
    """
    Provide some metadata on when this data dump has been made
    and which data source has been used for that.
    """

    name = 'phobos'

    def __init__(self, resbrowser):
        self._resbrowser = resbrowser
        self._container_name = 'metadata'

    def contname_iter(self):
        yield self._container_name

    def get_data(self, container_name, **kwargs):
        if container_name != self._container_name:
            self._container_not_found(container_name)
        else:
            file_info = self._resbrowser.get_file_info('app:/start.ini')
            field_names = ('field_name', 'field_value')
            container_data = []
            # Read client version
            try:
                config = ConfigParser()
                config.read(file_info.file_abspath)
                eve_version = config.getint('main', 'build')
            except KeyboardInterrupt:
                raise
            except:
                print(u'    failed to detect client version')
                eve_version = None
            container_data.append({field_names[0]: 'client_build', field_names[1]: eve_version})
            # Generate UNIX-style timestamp of current UTC time
            timestamp = int(time())
            container_data.append({field_names[0]: 'dump_time', field_names[1]: timestamp})
            return tuple(container_data)
