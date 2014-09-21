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


class Translator(object):
    """
    Class responsible for localization of different strings,
    according to language passed to reverence.
    """

    def __init__(self, rvr):
        self._cfg = rvr.getconfigmgr()
        # Format: {field name: [total entries, successes, failures]}
        self._stats = {}

    def translate(self, container_data):
        # Drop stats and run recursively on passed container
        self._stats.clear()
        self._route_object(container_data)
        self._print_stats()

    def _route_object(self, obj):
        """
        Pick proper method for passed object and invoke it.
        """
        obj_type = type(obj)
        # We should have normalized data here, thus all objects
        # we deal with should be standard python types. We go
        # through iterable and mapping types only, other types
        # do not need any processing
        if obj_type in self._translation_map:
            method = self._translation_map[obj_type]
            method(self, obj)

    def _translate_map(self, obj):
        """
        We can translate only data which is in map form,
        thus all the translation magic is in this method.
        """
        # First, attempt to do a pass over map key/values
        for key, value in obj.items():
            self._route_object(key)
            self._route_object(value)
        # Now, try to actually translate stuff
        # We assume that key we're dealing with is field name
        # whose value will reference translation, and after
        # we do few verification steps to confirm/deny this
        # claim
        for msgid_fname in obj:
            # It must be string in '<field name>ID' format
            if isinstance(msgid_fname, (str, unicode)) is False:
                continue
            suffix = 'ID'
            tail = msgid_fname[-len(suffix):]
            if tail != suffix:
                continue
            # There should be corresponding field which will
            # use this translation
            text_fname = msgid_fname[:-len(suffix)]
            if text_fname not in obj:
                continue
            # Past this, consider process as an attempt to translate
            self.__increment_stats(text_fname, 0)
            # MessageID should actually contain reference
            msgid = obj[msgid_fname]
            if not msgid:
                continue
            try:
                translation = self._cfg._localization.GetByMessageID(msgid)
            except KeyboardInterrupt:
                raise
            # When fetching translation fails, just fill in it
            # as failure and skip
            except:
                self.__increment_stats(text_fname, 2)
                continue
            # Translations might be just plain stubs, it's dumb to use
            # them instead of whatever could be in original text field
            if re.match('<NO TEXT, messageID=[0-9]+, param={.*}>', translation):
                continue
            # Finally, do translation
            obj[text_fname] = translation
            self.__increment_stats(text_fname, 1)

    def _translate_iterable(self, obj):
        """
        For iterables, request to make a pass over each
        child element.
        """
        for item in obj:
            self._route_object(item)

    _translation_map = {
        dict: _translate_map,
        tuple: _translate_iterable,
        list: _translate_iterable,
        set: _translate_iterable
    }

    def __increment_stats(self, field_name, place):
        """
        Increment some stat for given field:
        0 - total entries processed
        1 - successful translations
        2 - failures
        """
        try:
            statlist = self._stats[field_name]
        except KeyError:
            statlist = [0, 0, 0]
            self._stats[field_name] = statlist
        statlist[place] += 1

    def _print_stats(self):
        """
        Print stats for container which has just been translated.
        """
        for field_name in sorted(self._stats):
            total, trans, fails = self._stats[field_name]
            # When we didn't touch translations for some field,
            # do not print stats about it
            if not trans and not fails:
                continue
            elems = []
            elems.append('{} entries'.format(total))
            elems.append('{} translated'.format(trans))
            if fails:
                elems.append('{} failed'.format(fails))
            print(u'    field {}: {}'.format(field_name, ', '.join(elems)))
