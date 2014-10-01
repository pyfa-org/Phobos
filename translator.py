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
import types
from itertools import chain


class Translator(object):
    """
    Class responsible for text localization.
    """

    def __init__(self, pickle_miner):
        self._pminer = pickle_miner
        self.__available_langs = None
        # Format: {language code: {message ID: message text}}
        self._loaded_langs = {}
        # Format: {field name: [total entries, translated entries]}
        self._stats = {}
        # Variable which will indicate to which language we're
        # translating during current run
        self._requested_lang = None

    def translate(self, container_data, language):
        """
        Translate text fields in passed container
        to specified language.
        """
        if not language:
            return
        # Language code check against what we have in client
        supported_langs = tuple(chain(self._available_langs, ('multi',)))
        if language not in supported_langs:
            msg = u'language "{}" does not match any of available options: {}'.format(language, ', '.join(supported_langs))
            raise LanguageNotAvailable(msg)
        self._requested_lang = language
        self._stats.clear()
        self._route_object(container_data)
        self._print_stats()

    # Related to recursive translation

    def _route_object(self, obj):
        """
        Pick proper method for passed object and invoke it.
        """
        obj_type = type(obj)
        # We should have normalized data here, thus all objects
        # we deal with should be standard python types. We go
        # through iterable and mapping types only, other types
        # do not need any processing
        method = self._translation_map.get(obj_type)
        if method is not None:
            method(self, obj)

    def _translate_map(self, obj):
        """
        We can translate only data which is in map form,
        thus all the translation magic is in this method.
        """
        # First, attempt to do a pass over map key/values
        # (they are not always text)
        for key, value in obj.items():
            self._route_object(key)
            self._route_object(value)
        # Now, try to actually translate stuff
        # We assume that key we're dealing with is field name
        # whose value contains message ID, and after that
        # we do few verification steps to confirm/deny this
        # claim
        for text_fname, msgid_fname in self.__translatable_fields_iter(obj):
            self.__increment_stats(text_fname, 0)
            orig_text = obj[text_fname]
            msgid = obj[msgid_fname]
            # I didn't find a way to disable reverence localization engine
            # altogether, thus 'original' text isn't always 'raw' value
            # fetched from client - it might be translation. When reverence
            # fails to translate message - it writes some dumb-looking stub
            # there, and here we get rid of it
            if orig_text is not None and re.match('<NO TEXT, messageID=[0-9]+, param={.*}>', orig_text):
                orig_text = ''
            # Following are priorities when translating:
            # 1) Translation to target language
            # 2) Translation to english
            # 3) Original value
            # 4) Empty string
            # If 1st is not available (gets evaluated as False), we go to next
            # point and check its availability, and so on
            if self._requested_lang == 'multi':
                self.__translation_multimode(obj, text_fname, msgid, orig_text)
            else:
                self.__translation_singlemode(obj, text_fname, msgid, orig_text)

    def _translate_iterable(self, obj):
        """
        For iterables, request to make a pass over each
        child element.
        """
        for item in obj:
            self._route_object(item)

    _translation_map = {
        types.DictType: _translate_map,
        types.TupleType: _translate_iterable,
        types.ListType: _translate_iterable
    }

    def __translation_multimode(self, row, text_fname, msgid, orig_text):
        """
        Translate one field into multiple languages, and write them as
        additional fields (in the <field name>_<language> format). Leave
        original field untouched.
        """
        for language in self._available_langs:
            new_text_fname = u'{}_{}'.format(text_fname, language)
            if msgid is not None:
                trans_text = (
                    self._get_message(language, msgid) or
                    self._get_message('en-us', msgid) or
                    orig_text or
                    ''
                )
            else:
                trans_text = orig_text or ''
            # Always write translation, even if it's the same as
            # original text - rows should have the same set of
            # fields,regardless of translation availability
            row[new_text_fname] = trans_text
            # Increment counter only when translation is different
            if trans_text != orig_text:
                self.__increment_stats(text_fname, 1)

    def __translation_singlemode(self, row, text_fname, msgid, orig_text):
        """
        Translate one text field into single language. Translation
        is inplace.
        """
        if msgid is None:
            return
        trans_text = (
            self._get_message(self._requested_lang, msgid) or
            self._get_message('en-us', msgid) or
            orig_text or
            ''
        )
        row[text_fname] = trans_text
        if trans_text != orig_text:
            self.__increment_stats(text_fname, 1)

    def __translatable_fields_iter(self, row):
        """
        Receive dictionary, find there pairs of field
        names for translation, and yield them one by one.
        """
        suffix = 'ID'
        # We assume that key we're dealing with is field name
        # whose value contains message ID, and after that
        # we do few verification steps to confirm/deny this
        # claim
        for msgid_fname in row.keys():
            # It must be string in '<field name>ID' format, skip current
            # field name if it's not the case
            if isinstance(msgid_fname, types.StringTypes) is False:
                continue
            tail = msgid_fname[-len(suffix):]
            if tail != suffix:
                continue
            # There should be corresponding field which will
            # use this message ID (CCP's convention is fieldName /
            # fieldNameID pair)
            text_fname = msgid_fname[:-len(suffix)]
            if text_fname not in row:
                continue
            # Now, verify text field contents - it should be either
            # string type or None
            text = row[text_fname]
            if text is not None and isinstance(text, types.StringTypes) is False:
                continue
            yield (text_fname, msgid_fname)

    def __increment_stats(self, field_name, place):
        """
        Increment some stat for given field:
        0 - total entries processed
        1 - successful translations
        """
        try:
            statlist = self._stats[field_name]
        except KeyError:
            statlist = [0, 0]
            self._stats[field_name] = statlist
        statlist[place] += 1

    def _print_stats(self):
        """
        Print stats for container which has just been translated.
        """
        for field_name in sorted(self._stats):
            total, trans = self._stats[field_name]
            # When we didn't touch translations for some field,
            # do not print stats about it
            if not trans:
                continue
            print(u'    field {}: {} entries, {} translations'.format(field_name, total, trans))

    # Related to loading language data

    def _load_pickle(self, name):
        return self._pminer.get_data(name)

    def _load_lang(self, language):
        """
        Compose map between message IDs and message texts
        and put it into loaded languages map.
        """
        message_map = {}
        lang_data_old = self._load_pickle('res/localization/localization_{}'.format(language))
        lang_data_fsd = self._load_pickle('res/localizationfsd/localization_fsd_{}'.format(language))
        # Translations from FSD container have priority, unless they are
        # absent and specified in conventional container
        for lang_data in (lang_data_old, lang_data_fsd):
            for msgid, msg_data in lang_data[1].items():
                msg_text = msg_data[0]
                message_map[msgid] = msg_text or message_map.get(msgid) or ''
        self._loaded_langs[language] = message_map

    def _get_message(self, language, msgid):
        """
        Fetch message text for specified language and message ID,
        if language hasn't been loaded yet - load it. If no text
        found, return empty string.
        """
        try:
            message_map = self._loaded_langs[language]
        except KeyError:
            self._load_lang(language)
            message_map = self._loaded_langs[language]
        return message_map.get(msgid) or ''

    @property
    def _available_langs(self):
        """
        Returns list of available translation languages.
        """
        if self.__available_langs is None:
            languages = set()
            main_old = self._load_pickle('res/localization/localization_main')
            main_fsd = self._load_pickle('res/localizationfsd/localization_fsd_main')
            languages.update(main_old['languages'].keys())
            languages.update(main_fsd['languages'])
            self.__available_langs = tuple(sorted(languages))
        return self.__available_langs


class LanguageNotAvailable(Exception):
    """
    Raised when translator is asked to translate to language
    which it does not support.
    """
    pass
