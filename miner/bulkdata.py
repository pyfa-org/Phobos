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


class BulkdataMiner(AbstractMiner):
    """
    Class, responsible for fetching data out of bulkdata, which is included
    with EVE client.
    """

    def __init__(self, path_eve, path_cache, server):
        # Initialize reverence
        eve = blue.EVE(path_eve, cachepath=path_cache, server=server)
        self.cfg = eve.getconfigmgr()

    def tablename_iter(self):
        for table_name in self.cfg.tables:
            yield table_name

    def get_table(self, table_name):
        lines = []
        bulk_table = getattr(self.cfg, table_name)
        return lines
