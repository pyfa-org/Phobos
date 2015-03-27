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


class ResourceBrowser(object):
    """
    Class, responsible for browsing/retrieval of resources.
    """

    def __init__(self, rvr):
        self._rvr = rvr

    def get_filelist(self):
        """
        Aggregate filepaths from all resource files and return
        them in the form of single list.
        """
        return sorted(self._rvr.rescache._nameMap.keys())

    def get_file(self, resfilepath):
        """
        Return file contents for requested resource.
        """
        return self._rvr.readstuff(resfilepath)
