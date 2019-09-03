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


from abc import ABCMeta, abstractmethod


class BaseWriter(object):
    """
    Abstract class, which defines interface to classes
    which write data into some kind of persistent storage.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def write(self, writer_resolved_name, container_data):
        pass

    @abstractmethod
    def secure_name(self, flow_name):
        """
        Writers might need to modify container names proposed by
        flow (because names can have symbols not allowed to use
        on filesystems, in database table names, etc). This method
        should make name which is safe to use with particular writer.
        """
        pass

    @abstractmethod
    def resolve_name_collisions(self, flow_writersafe_map):
        """
        Take map between flow names and writer safe names, resolve
        collisions between safe names and return map between flow
        names and writer resolved names.
        """
        pass
