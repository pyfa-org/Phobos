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


from reverence import blue

from .abstract_miner import AbstractMiner
from .eve_normalize import EveNormalizer
from .exception import ContainerNameError


class BulkdataMiner(AbstractMiner):
    """
    Class, responsible for fetching data out of bulkdata, which is included
    with EVE client.
    """

    def __init__(self, path_eve, path_cache, server):
        # Initialize reverence
        eve = blue.EVE(path_eve, cachepath=path_cache, server=server)
        self.cfg = eve.getconfigmgr()

    def contname_iter(self):
        for container_name in sorted(self.cfg.tables):
            yield container_name

    def get_data(self, container_name):
        try:
            container_data = getattr(self.cfg, container_name)
        except AttributeError:
            msg = u'container "{}" is not available for miner {}'.format(container_name, type(self).__name__)
            raise ContainerNameError(msg)
        normalized_data = EveNormalizer().run(container_data)
        return normalized_data
