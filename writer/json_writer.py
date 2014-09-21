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
import re

from .abstract_writer import AbstractWriter


class JsonWriter(AbstractWriter):
    """
    Class, which stores fetched data on storage device
    as JSON files.
    """

    def __init__(self, folder, indent=None):
        self.folder = folder
        self.indent = indent

    def write(self, writer_resolved_name, container_data):
        # Create folder structure to path, if not created yet
        if not os.path.exists(self.folder):
            os.makedirs(self.folder, mode=0o755)
        json.dump(
            container_data,
            open(os.path.join(self.folder, '{}.json'.format(writer_resolved_name)), 'w'),
            indent=self.indent,
            encoding='cp1252'
        )

    def secure_name(self, flow_name):
        """
        As we're writing to disk, we should get rid of all
        filesystem-specific symbols.
        """
        # Prefer safe way - replace any characters besides
        # alphanumeric and few special characters with
        # underscore
        writer_safe_name = re.sub('[^\w\-\.,\(\) ]', '_', flow_name, flags=re.UNICODE)
        return writer_safe_name

    def resolve_name_collisions(self, flow_writersafe_map):
        # Intermediate map
        # Format: {safe writer name in lower case: [flow names]}
        writersafelow_flow_map = {}
        for flow_name, writer_safe_name in flow_writersafe_map.items():
            # We convert to lower case because 'file.json' and
            # 'File.json' are same names on windows - thus we
            # need to consider it as collision
            writer_safe_name_low = writer_safe_name.lower()
            flow_names = writersafelow_flow_map.setdefault(writer_safe_name_low, [])
            flow_names.append(flow_name)
        # Container for collision-free names
        # Format: {flow name: resolved writer name}
        flow_writerresolved_map = {}
        for flow_names in writersafelow_flow_map.values():
            # Resolve collisions by appending number suffix with 'writer'
            # marker to safe writer name (not converted to lower case)
            if len(flow_names) > 1:
                sorted_flow_names = sorted(flow_names)
                for i in range(len(sorted_flow_names)):
                    flow_name = sorted_flow_names[i]
                    writer_safe_name = flow_writersafe_map[flow_name]
                    writer_resolved_name = u'{}_w{}'.format(writer_safe_name, i + 1)
                    flow_writerresolved_map[flow_name] = writer_resolved_name
            # Map source to originally used safe name if no collisions
            else:
                flow_name = flow_names[0]
                writer_safe_name = flow_writersafe_map[flow_name]
                flow_writerresolved_map[flow_name] = writer_safe_name
        return flow_writerresolved_map
