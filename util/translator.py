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
import types

from miner import ContainerNameError


class Translator(object):
    """
    Class responsible for text localization.
    """

    def __init__(self, pickle_miner):
        self._pickle_miner = pickle_miner
        # Format: {language code: {message ID: message text}}
        self._loaded_langs = {}
        # Container for data we fetch from shared language data
        self.__available_langs = None
        self.__label_map = None

    def translate_container(self, container_data, language, spec=None, verbose=False):
        """
        Translate text fields in passed container
        to specified language.

        By default it attempts to do automatic translation
        (finds all pairs of fields in fieldName-fieldNameID
        format, uses ID to find translation and substitutes
        into fieldName[_language] field.

        If spec argument is passed (list of fieldNames which
        should be inserted into row, if fieldNameID is present),
        then it is used to detect translatable fields instead
        of automatic detection.
        """
        if not language:
            return
        stats = {}
        self._route_object(container_data, language, spec, stats)
        if verbose:
            self._print_current_stats(stats)

    # Related to recursive translation

    def _route_object(self, obj, language, spec, stats):
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
            method(self, obj, language, spec, stats)

    def _translate_map(self, obj, language, spec, stats):
        """
        We can translate only data which is in map form,
        thus all the translation magic is in this method.
        """
        # First, attempt to do a pass over map key/values
        # (they are not always text)
        for key, value in obj.items():
            self._route_object(key, language, spec, stats)
            self._route_object(value, language, spec, stats)
        # Now, try to actually translate stuff
        for text_fname, msgid_fname in self.__translatable_fields_iter(obj, spec):
            self.__increment_stats(stats, text_fname, 0)
            orig_text = obj.get(text_fname, '')
            msgid = obj[msgid_fname]
            # Following are priorities when translating:
            # 1) Translation to target language
            # 2) Translation to english
            # 3) Original value
            # 4) Empty string
            # If 1st is not available (gets evaluated as False), we go to next
            # point and check its availability, and so on
            if language == 'multi':
                self.__translation_multimode(obj, text_fname, msgid, orig_text, stats)
            else:
                self.__translation_singlemode(obj, text_fname, msgid, language, orig_text, stats)

    def _translate_iterable(self, obj, language, spec, stats):
        """
        For iterables, request to make a pass over each
        child element.
        """
        for item in obj:
            self._route_object(item, language, spec, stats)

    _translation_map = {
        types.DictType: _translate_map,
        types.TupleType: _translate_iterable,
        types.ListType: _translate_iterable
    }

    def __translation_multimode(self, row, text_fname, msgid, orig_text, stats):
        """
        Translate one field into multiple languages, and write them as
        additional fields (in the <field name>_<language> format). Leave
        original field untouched.
        """
        for language in self.available_langs:
            new_text_fname = u'{}_{}'.format(text_fname, language)
            if msgid is not None:
                trans_text = (
                    self.get_by_message(msgid, language) or
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
                self.__increment_stats(stats, text_fname, 1)

    def __translation_singlemode(self, row, text_fname, msgid, language, orig_text, stats):
        """
        Translate one text field into single language. Translation
        is inplace.
        """
        if msgid is None:
            return
        trans_text = (
            self.get_by_message(msgid, language) or
            orig_text or
            ''
        )
        row[text_fname] = trans_text
        if trans_text != orig_text:
            self.__increment_stats(stats, text_fname, 1)

    # Regular expression to detect message ID fields for translation
    _keyword_regexp = re.compile('^.*({}).*$'.format('|'.join(('description', 'name', 'text'))), flags=re.IGNORECASE)

    def __translatable_fields_iter(self, row, spec):
        """
        Receive dictionary, find there pairs of field
        names for translation, and yield them one by one.
        """
        suffix = 'ID'
        if spec is None:
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
                # Message ID can None or integer
                msgid = row[msgid_fname]
                if msgid is not None and isinstance(msgid, (types.IntType, types.LongType)) is False:
                    continue
                # There're 2 conventions which CCP use for text and message fields:
                # 1) There're pair of fields named like fieldName / fieldNameID pair
                # 2) For cases when there's no fieldName, we rely on name of fieldNameID
                # field - it should contain one of the keywords like 'name' to be translated
                text_fname = msgid_fname[:-len(suffix)]
                # FIrst convention
                if text_fname in row:
                    # Text can be string or None
                    text = row[text_fname]
                    if text is not None and isinstance(text, types.StringTypes) is False:
                        continue
                    # If both text and message ID are None, skip them to avoid
                    # unnecessary translations (which can convert None to empty
                    # string which is undesired in some cases)
                    if text is None and msgid is None:
                        continue
                # Second convention
                elif re.match(self._keyword_regexp, text_fname):
                    # We don't have anything to check here
                    pass
                # Skip field names which don't fit into any of these 2 conventions
                else:
                    continue
                yield (text_fname, msgid_fname)
        else:
            for text_fname in spec:
                msgid_fname = u'{}{}'.format(text_fname, suffix)
                # Skip all message ID fields which are not present in row
                if msgid_fname not in row:
                    continue
                yield (text_fname, msgid_fname)


    def __increment_stats(self, stats, field_name, place, amount=1):
        """
        Increment some stat for given field:
        0 - total entries processed
        1 - successful translations
        """
        try:
            statlist = stats[field_name]
        except KeyError:
            statlist = [0, 0]
            stats[field_name] = statlist
        statlist[place] += amount

    def _print_current_stats(self, stats):
        """
        Print stats for container which has just been translated.
        """
        for field_name in sorted(stats):
            total, trans = stats[field_name]
            # When we didn't touch translations for some field,
            # do not print stats about it
            if not trans:
                continue
            print(u'    field {}: {} entries, {} translations'.format(field_name, total, trans))

    # Related to loading language data
    def _load_pickle(self, name):
        return self._pickle_miner.get_data(name)

    def _load_lang_data(self, language):
        """
        Compose map between message IDs and message texts
        and put it into loaded languages map.
        """
        try:
            lang_data_eve = self._load_pickle(u'res:/localizationfsd/localization_fsd_{}'.format(language))
        except ContainerNameError:
            msg = u'data for language "{}" cannot be loaded'.format(language)
            raise LanguageNotAvailable(msg)
        msg_map_phb = lang_data_eve[1]
        self._loaded_langs[language] = msg_map_phb

    def _get_language_data(self, lang):
        """
        Get language data and return it; if it's not
        loaded yet - load.
        """
        try:
            lang_data = self._loaded_langs[lang]
        except KeyError:
            self._load_lang_data(lang)
            lang_data = self._loaded_langs[lang]
        return lang_data

    _msg_data_stub = ('', None, {})

    def get_by_message(self, msgid, lang, fallback_lang='en-us', **kwargs):
        """
        Fetch message text for specified language and message ID.
        If text is empty, attempt to use fallback language. If
        it is not found too, return empty string.
        """
        try:
            lang_data = self._get_language_data(lang)
        except LanguageNotAvailable:
            lang_data = self._get_language_data(fallback_lang)
        msg_data = lang_data.get(msgid, self._msg_data_stub)
        # Use fallback language  only when fetching text for primary
        # language failed, and when fallback language doesn't match
        # primary language
        if not msg_data[0] and fallback_lang is not None and lang != fallback_lang:
            lang_data_fb = self._get_language_data(fallback_lang)
            msg_data = lang_data_fb.get(msgid, self._msg_data_stub)
        text = self._format_message(msg_data, kwargs)
        return text

    def get_by_label(self, label, *args, **kwargs):
        """
        Fetch message text for specified language and label.
        If label cannot be found, raise exception. If no text
        found, return empty string.
        """
        try:
            msgid = self._label_map[label]
        except KeyError:
            msg = u'label {} does not exist'.format(label)
            raise LabelError(msg)
        return self.get_by_message(msgid, *args, **kwargs)

    def _format_message(self, msg_data, kwargs):
        """
        Take message data and substitute passed arguments
        into it, then return final message text.
        """
        text, _, tokens = msg_data
        # Tokens may be None
        if not tokens:
            return text
        for tok_name, tok_data in tokens.items():
            arg_name = tok_data['variableName']
            try:
                substitution = kwargs[arg_name]
            except KeyError:
                continue
            text = text.replace(tok_name, unicode(substitution))
        return text

    @property
    def available_langs(self):
        """
        Returns list of available translation languages.
        """
        if self.__available_langs is None:
            self._load_shared_data()
        return self.__available_langs

    @property
    def _label_map(self):
        """
        Map between labels and message IDs.
        Format: {full/path/to/label: message ID}
        """
        if self.__label_map is None:
            self._load_shared_data()
        return self.__label_map

    def _load_shared_data(self):
        """
        To avoid loading same pickles twice, fetch necessary data
        from them here and assign to proper attributes. This method
        is intended to be called when any of shared data is requested.
        """
        lbl_map_phb = {}
        main_eve = self._load_pickle('res:/localizationfsd/localization_fsd_main')
        # Load list of languages
        languages = set(main_eve['languages'])
        self.__available_langs = tuple(sorted(languages))
        # Load label map
        for msgid in sorted(main_eve['labels']):
            lbl_data = main_eve['labels'][msgid]
            lbl_base = lbl_data.get('FullPath')
            lbl_name = lbl_data.get('label')
            lbl_components = []
            if lbl_base:
                lbl_components.append(lbl_base)
            if lbl_name:
                lbl_components.append(lbl_name)
            lbl_path = u'/'.join(lbl_components)
            lbl_map_phb[lbl_path] = msgid
        self.__label_map = lbl_map_phb


class LanguageNotAvailable(Exception):
    """
    Raised when translator is asked to translate to language
    which it does not support.
    """
    pass


class LabelError(Exception):
    """
    Raised when requested label cannot be found.
    """
    pass
