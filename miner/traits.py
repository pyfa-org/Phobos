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


import re

from .base import BaseMiner


tags = re.compile('<.+?>')


def striptags(text):
    return tags.sub('', text)


class TraitMiner(BaseMiner):
    """
    Phobos actually dumps all the required data needed
    to compose item traits. We're doing it internally for
    convenience of phobos users anyway.
    """

    name = 'phobos'

    def __init__(self, fsdlite_miner, fsdbinary_miner, translator):
        self._fsdlite_miner = fsdlite_miner
        self._fsdbinary_miner = fsdbinary_miner
        self._translator = translator
        self._container_name = 'traits'
        # Format: {language: {type ID: type name}}
        self._type_name_map_all = {}
        # Format: {language: {unit ID: unit display name}}
        self._unit_display_map_all = {}

    def contname_iter(self):
        yield self._container_name

    def get_data(self, container_name, language='en-us', **kwargs):
        if container_name != self._container_name:
            self._container_not_found(container_name)
        else:
            return self._all_traits(language)

    def _all_traits(self, language):
        """
        Compose list of traits. Format:
        Returned value:
        For single language: ({'typeID': int, 'traits': traits}, ...)
        For multi-language: ({'typeID': int, 'traits_en-us': traits, 'traits_r': traits, ...}, ...)
        Traits: {'skills': (skill section, ...), 'role': role section, 'misc': misc section}
          skills, role and misc fields are optional
        Section: {'header': string, 'bonuses': (bonus, ...)}
        Bonus: {'number': string, 'text': string}
          number field is optional
        """
        trait_rows = []
        bubble_data = self._fsdlite_miner.get_data('infobubbles')
        for type_id, trait_data in bubble_data['infoBubbleTypeBonuses'].items():
            type_id = int(type_id)
            trait_row = {'typeID': type_id}
            # For multi-language, each trait row will contain traits for
            # all languages in fields named like traits_en-us
            if language == 'multi':
                for mlanguage in self._translator.available_langs:
                    traits_header = 'traits_{}'.format(mlanguage)
                    traits = self._type_traits(trait_data, mlanguage)
                    trait_row[traits_header] = traits
            # For single language, we will have just single field named
            # traits
            else:
                traits = self._type_traits(trait_data, language)
                trait_row['traits'] = traits
            trait_rows.append(trait_row)
        return tuple(trait_rows)

    def _type_traits(self, trait_data, language):
        """
        Return traits for single item.
        """
        traits = {}
        # Go through skill-based traits first
        if "types" in trait_data:
            skill_ids = [int(k) for k in trait_data["types"].keys()]
            if skill_ids:
                skill_rows = []
                for skill_typeid in skill_ids:
                    skill_name = self._get_type_name(skill_typeid, language)
                    section_header = self._translator.get_by_label('UI/ShipTree/SkillNameCaption', language, skillName=skill_name)
                    section_data = trait_data['types'][str(skill_typeid)]
                    bonuses = self._section_bonuses(section_data, language)
                    skill_row = {'header': section_header, 'bonuses': bonuses}
                    skill_rows.append(skill_row)
                traits['skills'] = tuple(skill_rows)

        # Then traits for all known special sections
        for special_type, special_label, cont_alias in (
            ('roleBonuses', 'UI/ShipTree/RoleBonus', 'role'),
            ('miscBonuses', 'UI/ShipTree/MiscBonus', 'misc')
        ):
            if special_type not in trait_data:
                continue
            section_header = self._translator.get_by_label(special_label, language)
            section_data = trait_data[special_type]
            if len(section_data) == 0:
                continue
            bonuses = self._section_bonuses(section_data, language)
            special_row = {'header': section_header, 'bonuses': bonuses}
            traits[cont_alias] = special_row
        return traits

    def _section_bonuses(self, section_data, language):
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
        sorted_bonuses = sorted(section_data, key=lambda k: k['importance'])
        for bonus_data in sorted_bonuses:
            #bonus_data = section_data[str(bonus_index)]
            bonus_msgid = bonus_data['nameID']
            bonus_text = self._translator.get_by_message(bonus_msgid, language)
            bonus_amt = bonus_data.get('bonus')
            # Bonuses can be with numerical value and without it, they have different
            # processing. Also, they are flooded with various HTML tags, we strip them
            # here.
            if bonus_amt is not None:
                # Some bonuses are represented as non-rounded float, like
                # 33.2999992371 for Confessor's defensive mode resistance bonus,
                # here we make sure it's properly rounded to values like 33.3
                bonus_amt = round(bonus_amt, 5)
                if int(bonus_amt) == bonus_amt:
                    bonus_amt = int(bonus_amt)
                unit = self._get_unit_displayname(bonus_data['unitID'], language)
                bonus = self._translator.get_by_label(
                    'UI/InfoWindow/TraitWithNumber',
                    language,
                    color='',
                    value=bonus_amt,
                    unit=unit,
                    bonusText=bonus_text)
                number, text = (striptags(t) for t in bonus.split('<t>'))
                bonus_row = {'number': number, 'text': text}
            else:
                bonus = self._translator.get_by_label(
                    'UI/InfoWindow/TraitWithoutNumber',
                    language,
                    color='',
                    bonusText=bonus_text)
                text = striptags(bonus)
                bonus_row = {'text': text}
            bonuses.append(bonus_row)
        return tuple(bonuses)

    def _get_type_name(self, typeid, language):
        """
        Get translated name for specified type and language.
        """
        try:
            type_name_map = self._type_name_map_all[language]
        except KeyError:
            types = self._fsdbinary_miner.get_data('types', language=language)
            type_name_map = {}
            for type_id, type_row in types.items():
                type_id = int(type_id)
                type_name_map[type_id] = type_row.get('typeName')
            self._type_name_map_all[language] = type_name_map
        return type_name_map[typeid]

    def _get_unit_displayname(self, unitid, language):
        """
        Get unit display name for specified type and language.
        """
        try:
            unit_display_map = self._unit_display_map_all[language]
        except KeyError:
            dgmunits = self._fsdbinary_miner.get_data('dogmaunits', language=language)
            unit_display_map = {}
            for unit_id, unit_data in dgmunits.items():
                unit_display_map[unit_id] = unit_data.get('displayName')
            self._unit_display_map_all[language] = unit_display_map
        return unit_display_map[unitid]
