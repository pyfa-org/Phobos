#===============================================================================
# Copyright (C) 2012 Diego Duclos
# Copyright (C) 2013-2014 Anton Vorobyov
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


CONTAINER_MAP = {
}


class EveNormalizer(object):
    """
    Class, which 'flattens' indexed structures into list of
    'rows' and converts all eve-specific data structures into
    python built-in types.
    """
    __metaclass__ = ABCMeta

    def __new__(cls, eve_container):
        container_type = getattr(eve_container, '__guid__', eve_container.__class__.__name__)
        return object.__new__(CONTAINER_MAP[container_type], eve_container)

    def __init__(self, eve_container):
        self.eve_container = eve_container

    def run(self):
        return self._get_lines()

    @abstractmethod
    def _get_lines(self):
        pass

