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
from time import time

from .abstract_miner import AbstractMiner


class MetadataMiner(AbstractMiner):
    """
    Provide some metadata on when this data dump has been made
    and which data source has been used for that.
    """

    def __init__(self, path_eve):
        self._container_name = self._secure_name('phbmetadata')
        self._path_eve = path_eve

    def contname_iter(self):
        for resolved_name in (self._container_name,):
            yield resolved_name

    def get_data(self, resolved_name, **kwargs):
        if resolved_name != self._container_name:
            self._container_not_found(resolved_name)
        else:
            field_names = ('field_name', 'field_value')
            container_data = []
            # Read client version
            try:
                config = ConfigParser()
                config.read(os.path.join(self._path_eve, 'start.ini'))
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
