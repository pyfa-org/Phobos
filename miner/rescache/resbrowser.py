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


import csv
import os.path


class ResourceBrowser(object):
    """
    Class, responsible for browsing/retrieval of resources.
    """

    def __init__(self, path_eve, path_resources):
        # Get resource file list
        # Format:
        # {embedFS file name: full path to file}
        self._resfiles = {}
        path_index = os.path.join(path_eve, 'resfileindex.txt')
        with open(path_index) as csvfile:
            index_reader = csv.reader(csvfile)
            for row in index_reader:
                embedfs_path = row[0]
                resource_path = os.path.join(path_resources, 'ResFiles', row[1])
                self._resfiles[embedfs_path] = resource_path

    def get_filelist(self):
        """
        Aggregate filepaths from all resource files and return
        them in the form of single list.
        """
        return sorted(self._resfiles)

    def get_file(self, embedfs_path):
        """
        Return file contents for requested resource.
        """
        resource_path = self._resfiles[embedfs_path]
        with open(resource_path) as f:
            data = f.read()
        return data
