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


from itertools import chain


class Unstuffer(object):
    """
    Class, responsible for browsing virtual filesystem of
    .stuff files and read data from there.
    """

    def __init__(self, rvr):
        self._efs = rvr.rot.efs

    def get_filelist(self):
        """
        Aggregate filepaths from all .stuff files and return
        them in the form of single list.
        """
        resfilepaths = chain(*(stuff.files for stuff in self._efs.stuff))
        return sorted(resfilepaths)

    def get_file(self, resfilepath):
        """
        Return file contents for requested resource located
        on .stuff filesystem.
        """
        return self._efs.open(resfilepath).read()
