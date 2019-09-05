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


from util import CachedProperty
from .base import BaseMiner
from .eve_normalize import EveNormalizer


class BulkdataMiner(BaseMiner):
    """
    Class, responsible for fetching data out of bulkdata, which is included
    with EVE client.
    """

    name = 'bulkdata'

    def __init__(self, rvr, translator):
        self._cfg = rvr.getconfigmgr()
        self._translator = translator

    def contname_iter(self):
        for container_name in sorted(self._cfg.tables):
            yield container_name

    def get_data(self, container_name, language=None, verbose=False, **kwargs):
        container_data = getattr(self._cfg, container_name)
        normalized_data = EveNormalizer().run(container_data)
        self._translator.translate_container(normalized_data, language, verbose=verbose)
        return normalized_data
