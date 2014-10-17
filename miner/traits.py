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


import re

from util import CachedProperty
from .abstract_miner import AbstractMiner


ROLE_BONUS_TYPE = -1
MISC_BONUS_TYPE = -2
SPECIAL_TYPES = (
    ROLE_BONUS_TYPE,
    MISC_BONUS_TYPE
)


tags = re.compile('\<.+?\>')


def striptags(text):
    return tags.sub('', text)


class TraitMiner(AbstractMiner):
    """
    Actually, phobos dumps all the required data needed
    to compose item traits. We're doing it internally for
    convenience of phobos users anyway.
    """

    def __init__(self, bulkminer, translator):
        self._container_name = self._secure_name('phbtraits')
        self._bulkminer = bulkminer
        self._translator = translator

    def contname_iter(self):
        for resolved_name in (self._container_name,):
            yield resolved_name

    def get_data(self, resolved_name, language='en-us', **kwargs):
        if resolved_name != self._container_name:
            self._container_not_found(resolved_name)
        else:
            return self._all_traits()

    def _all_traits(self):
        """
        Compose list of traits. Format:
        Returned value: ({'typeID': int, 'traits' traits}, ...)
        Traits: {'skills': (skill section, ...), 'role': role section, 'misc': misc section}
        --skills, role and misc fields are optional
        Section: {'header': string, 'bonuses': (bonus, ...)}
        Bonus: {'number': string, 'text': string}
        --number field is optional
        """
        trait_rows = []
        for type_id, type_data in self._bulkminer.get_data('fsdTypeOverrides').items():
            trait_data = type_data.get('infoBubbleTypeBonuses')
            if trait_data is None:
                continue
            traits = self._type_traits(trait_data)
            trait_row = {'typeID': type_id, 'traits': traits}
            trait_rows.append(trait_row)
        return tuple(trait_rows)

    def _type_traits(self, trait_data):
        """
        Return traits for single item.
        """
        traits = {}
        # Go through skill-based traits first
        skill_ids = list(filter(lambda i: i not in SPECIAL_TYPES, trait_data))
        if skill_ids:
            skill_rows = []
            for skill_typeid in skill_ids:
                skill_name = self._type_name_map[skill_typeid]
                section_header = self._translator.get_by_label('UI/ShipTree/SkillNameCaption', 'en-us', skillName=skill_name)
                section_data = trait_data[skill_typeid]
                bonuses = self._section_bonuses(section_data)
                skill_row = {'header': section_header, 'bonuses': bonuses}
                skill_rows.append(skill_row)
            # Sort skill sections by headers
            traits['skills'] = tuple(sorted(skill_rows, key=lambda r: r['header']))
        # Then traits for all known special sections
        for special_typeid, special_label, cont_alias in (
            (ROLE_BONUS_TYPE, 'UI/ShipTree/RoleBonus', 'role'),
            (MISC_BONUS_TYPE, 'UI/ShipTree/MiscBonus', 'misc')
        ):
            if special_typeid not in trait_data:
                continue
            section_header = self._translator.get_by_label(special_label, 'en-us')
            section_data = trait_data[special_typeid]
            bonuses = self._section_bonuses(section_data)
            special_row = {'header': section_header, 'bonuses': bonuses}
            traits[cont_alias] = special_row
        return traits

    def _section_bonuses(self, section_data):
        """
        Receive section data, in the format it is stored
        in client, and convert it to phobos-specific format
        with actual bonuses description. Section is part of
        what you see in traits table - e.g. bonuses from one
        skill with header (there can be multiple).
        """
        bonuses = []
        # Use sorting as defined by EVE (index seems to be not used
        # for anything apart from this)
        for bonus_index in sorted(section_data):
            bonus_data = section_data[bonus_index]
            bonus_msgid = bonus_data['nameID']
            bonus_text = self._translator.get_by_message(bonus_msgid, 'en-us')
            bonus_amt = bonus_data.get('bonus')
            # Bonuses can be with numerical value and without it, they have different
            # processing. Also, they are flooded with various HTML tags, we strip them
            # here.
            if bonus_amt is not None:
                if int(bonus_amt) == bonus_amt:
                    bonus_amt = int(bonus_amt)
                unit = self._unit_display_map[bonus_data['unitID']]
                bonus = self._translator.get_by_label(
                    'UI/InfoWindow/TraitWithNumber',
                    'en-us',
                    color='',
                    value=bonus_amt,
                    unit=unit,
                    bonusText=bonus_text
                )
                number, text = (striptags(t) for t in bonus.split('<t>'))
                bonus_row = {'number': number, 'text': text}
            else:
                bonus = self._translator.get_by_label(
                    'UI/InfoWindow/TraitWithoutNumber',
                    'en-us',
                    color='',
                    bonusText=bonus_text
                )
                text = striptags(bonus)
                bonus_row = {'text': text}
            bonuses.append(bonus_row)
        return tuple(bonuses)

    @CachedProperty
    def _type_name_map(self):
        """
        Format: {type ID: type name}
        """
        type_name_map = {}
        invtypes = self._bulkminer.get_data('invtypes', language='en-us')
        for row in invtypes:
            type_name_map[row['typeID']] = row.get('typeName')
        return type_name_map

    @CachedProperty
    def _unit_display_map(self):
        """
        Format: {unit ID: unit display name}
        """
        unit_display_map = {}
        dgmunits = self._bulkminer.get_data('dgmunits', language='en-us')
        for row in dgmunits:
            unit_display_map[row['unitID']] = row.get('displayName')
        return unit_display_map
