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


import pickle

from miner.abstract_miner import AbstractMiner
from .unstuff import Unstuffer


class PickleMiner(AbstractMiner):
    """
    Class, which attempts to get data from stuffed
    pickles (this is not guaranteed to succeed).
    """

    def __init__(self, rvr):
        self._pickle_ext = '.pickle'
        self._unstuffer = Unstuffer(rvr)

    def contname_iter(self):
        """
        Iterate over pickle resource file paths.
        """
        for resfilepath in self._unstuffer.get_filelist():
            if resfilepath.endswith(self._pickle_ext):
                resfilepath_noext = resfilepath[:-len(self._pickle_ext)]
                yield resfilepath_noext

    def get_data(self, resfilepath_noext):
        """
        Fetch pickle file contents, load it and return result.
        """
        resfilepath = '{}{}'.format(resfilepath_noext, self._pickle_ext)
        resfiledata = self._unstuffer.get_file(resfilepath)
        data = pickle.loads(resfiledata)
        return data
