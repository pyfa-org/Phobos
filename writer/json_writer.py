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


import json
import os.path

from .abstract_writer import AbstractWriter


class JsonWriter(AbstractWriter):
    def __init__(self, folder, indent=None):
        self.folder = folder
        self.indent = indent

    def write(self, table_name, lines):
        if not os.path.exists(self.folder):
            os.makedirs(self.folder, mode=0o755)
        json.dump(
            lines,
            open(os.path.join(self.folder, '{}.json'.format(table_name)), 'w'),
            indent=self.indent,
            encoding='cp1252'
        )
