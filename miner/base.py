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


class BaseMiner(object):
    """
    Abstract class, which defines interface to all data miners
    used in Phobos.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def contname_iter(self):
        """Provide an iterator over containers provided by miner."""
        raise NotImplementedError

    @abstractmethod
    def get_data(self, container_name, **kwargs):
        """Fetch data from specified container."""
        raise NotImplementedError

    @property
    def name(self):
        """Return miner group name, which can be used as output affix."""
        return self.raw_name

    @property
    def raw_name(self):
        """Return miner class name."""
        return type(self).__name__

    def _container_not_found(self, cont_name):
        msg = u'container "{}" is not available for miner {}'.format(cont_name, type(self).__name__)
        raise ContainerNameError(msg)


class ContainerNameError(Exception):
    """
    When container with requested name is not available,
    this exception is raised by miners.
    """
    pass
