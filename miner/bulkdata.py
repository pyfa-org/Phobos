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


from util import EveNormalizer
from .base import BaseMiner


bulkdata_map = {
    600005: 'invtypematerials',
    600006: 'invmetagroups',
    600007: 'invmetatypes',
    600008: 'invcontrabandtypes',
    600010: 'invtypereactions',
    800003: 'dogmaexpressions',
    800004: 'dogmaattributes',
    800005: 'dogmaeffects',
    800006: 'dogmatypeattributes',
    800007: 'dogmatypeeffects',
    800009: 'dogmaunits',
    1400002: 'maplocationwormholeclasses',
    1400008: 'mapcelestialdescriptions',
    1400016: 'mapnebulas',
    1800001: 'ramtyperequirements',
    1800003: 'ramactivities',
    1800004: 'ramassemblylinetypescategory',
    1800005: 'ramassemblylinetypesgroup',
    1800006: 'ramassemblylinetypes',
    1800007: 'ramcompletedstatuses',
    2000001: 'shiptypes',
    2209987: 'stastationsstatic',
    2209999: 'staoperations',
    2800006: 'crpnpccorporations',
    2809992: 'crptickernamesstatic',
    3000012: 'agentepicarcs',
    3000013: 'agentepicarcconnections',
    3000015: 'agentepicarcmissions',
    3009996: 'agentepicmissionmessages',
    3200001: 'chrraces',
    3200002: 'chrbloodlines',
    3200010: 'chrbloodlinenames',
    3200011: 'chrdefaultoverviews',
    3200012: 'chrdefaultoverviewgroups',
    3200015: 'chrfactions',
    3200016: 'chrnpccharacters',
    6400004: 'actbilltypes',
    7300003: 'planetschematicspinmap',
    7300004: 'planetschematics',
    7300005: 'planetschematicstypemap',
    7309999: 'planetblacklist',
    100300014: 'mapdistricts',
    100300015: 'mapbattlefields',
    100300020: 'maplevels',
    372833782: 'mapplanetsresources'}


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
