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


from abc import ABCMeta, abstractmethod


class BaseWriter(object):
    """
    Abstract class, which defines interface to classes
    which write data into some kind of persistent storage.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def write(self, miner_name, container_name, container_data):
        raise NotImplementedError
