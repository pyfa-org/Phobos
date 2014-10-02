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


from abc import ABCMeta, abstractmethod


class AbstractMiner(object):
    """
    Abstract class, which defines interface to all data miners
    used in Phobos.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def contname_iter(self):
        """
        Provide an iterator over containers provided by miner.
        """
        pass

    @abstractmethod
    def get_data(self, resolved_name):
        """
        Fetch data from specified container.
        """
        pass

    def _secure_name(self, source_name, arg=False):
        """
        We rely on container/service/call/arguments names to not have
        any parenthesis or commas, because these are special symbols -
        they split up arguments from calls and arguments from each
        other. Having these in names themselves would make it
        impossible to parse list of names passed to phobos.

        arg keyword argument defines if we're securing argument or not,
        arguments and non-arguments have slightly different handling.
        """
        # Make sure to convert to unicode, just in case argument of
        # non-string-type is passed
        safe_name = unicode(source_name)
        # We replace them with similar symbol instead of just removing
        safe_name = safe_name.replace('(', '<')
        safe_name = safe_name.replace(')', '>')
        safe_name = safe_name.replace(',', '.')
        # Table/service/call names should not have any whitespace characters
        if not arg:
            safe_name = safe_name.strip()
        return safe_name

    def _container_not_found(self, cont_name):
        msg = u'container "{}" is not available for miner {}'.format(cont_name, type(self).__name__)
        raise ContainerNameError(msg)


class ContainerNameError(Exception):
    """
    When container with requested name is not available,
    this exception is raised by miners.
    """
    pass
