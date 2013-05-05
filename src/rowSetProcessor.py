#===============================================================================
# Copyright (C) 2012 Diego Duclos
# Copyright (C) 2013 Anton Vorobyov
#
# This code is free software; you can redistribute it and/or modify
# it under the terms of the BSD license (see the file LICENSE.txt
# included with the distribution).
#===============================================================================


"""
RowProcessing entry point, will initialize a subclass of
the correct type to process the given rowset
"""

from abc import ABCMeta, abstractmethod
import reverence.fsd
from reverence.blue import DBRow
from phobos.writer.jsonWriter import JsonWriter
from copy import copy
from reverence.config import _localized


class RowSetProcessor:
    """Main row set processing class"""
    __metaclass__ = ABCMeta

    def __new__(cls, tableName, rowSet, cfg):
        typeId = getattr(rowSet, '__guid__', rowSet.__class__.__name__)
        return object.__new__(typeMap.get(typeId, Row), tableName, rowSet, cfg)

    def __init__(self, tableName, rowSet, cfg):
        self.rowSet = rowSet
        self.tableName = tableName
        self.cfg = cfg

    def run(self):
        guid = getattr(self.rowSet, "__guid__", None)
        cfg = self.cfg

        header = self.getHeader()
        lines = self.getLines(header)

        # Process localizations
        for k in header:
            warned = False
            # If the key ends with ID and we have an identical key that doesn't, we need to grab a translation
            if k[-2:] == "ID":
                if k[:-2] in header:
                    # Both keys exist, grab localizations
                    # First, figure out what ids we need to change data at
                    localIdIdx = header.index(k)
                    textIdx = header.index(k[:-2])
                    for line in lines:
                        try:
                            line[textIdx] = self.cfg._localization.GetByMessageID(line[localIdIdx])[0]
                        except:
                            if not warned:
                                print("Translation failed on {}[{}]".format(self.tableName, k))
                                warned = True

        return header, lines

    @abstractmethod
    def getHeader(self):
        pass

    @abstractmethod
    def getLines(self):
        pass

# Row handlers
class Row(RowSetProcessor):
    """Simplest row type possible"""
    def getHeader(self):
        return self.rowSet.header

    def getLines(self, header):
        return self.rowSet.lines

class Dict(RowSetProcessor):
    """RowSet is a dictionary"""
    def getHeader(self):
        """
        Dicts may contain lists of DbRows as values, acting much like IndexedRowLists
        However, they can contain multiple levels, we only need the deepest one
        """
        # Check all levels recursivly, we can't just check the first row and see whats there due to optional rows possible messing that up
        return self._getHeader(self.rowSet)

    def _getHeader(self, curr):
        header = set()
        if isinstance(curr, dict):
            for v in curr.itervalues():
                header.update(self._getHeader(v))
        elif isinstance(curr, list):
            for v in curr:
                header.update(self._getHeader(v))
        elif isinstance(curr, DBRow):
            return curr.__header__.Keys()
        elif isinstance(curr, tuple):
            # If we're dealing with a tuple, we have no choice but to generate keys ourselves
            return range(len(curr))
        else:
            # Fallback, assume we're dealing with a single primitive type, aka, a key:value dict with no strings attached
            return {'key', 'value'}

        return header

    def getLines(self, header):
        return self._getLines(header, self.rowSet)

    def _getLines(self, header, curr, key=None):
        lines = []
        if isinstance(curr, dict):
            for k, v in curr.iteritems():
                lines.extend(self._getLines(header, v, k))
        elif isinstance(curr, list):
            for v in curr:
                lines.extend(self._getLines(header, v))
        elif isinstance(curr, tuple):
            line = {}
            for i in xrange(len(curr)):
                line[i] = curr[i]

            lines.append(line)

        elif isinstance(curr, DBRow):
            lines.append(curr)
        else:
            lines.append({'key': key, 'value': curr})

        return lines

class FilterRowSet(Row):
    def getLines(self, header):
        """FilterRowSet contain a list of keyed data and then filterable info below it"""
        data = []
        rowSet = self.rowSet
        hRange = range(len(header))

        for key in rowSet.iterkeys():
            val = rowSet[key]
            for dataList in val.Select(*header):
                # Data is indexed by id, in the order passed with the header
                data.append({header[i]: dataList[i] for i in hRange})

        return data

class FsdLoader(RowSetProcessor):
    """FSD loader"""

    def getHeader(self):
        header = ['id'] + self.rowSet.schema['valueTypes']['attributes'].keys()
        return header

    def getLines(self, header):
        # As we process id field manually, remove it
        # from header list
        header = filter(lambda h: h != 'id', header)

        data = []

        for id_, fsdContainer in self.rowSet.iteritems():
            datarow = {}
            for h in header:
                # Get method is not available
                try:
                    datarow[h] = fsdContainer[h]
                except KeyError:
                    datarow[h] = None

            if len(datarow) > 0:
                datarow['id'] = id_
                data.append(datarow)

        return data

class IndexedRowLists(RowSetProcessor):
    def getHeader(self):
        """
        Indexed row lists are difficult, they have no global header.
        Loop through each row and check each of their keys to compose the header
        (The first row is not sufficient due to optional keys possibly not being mentioned there)
        """
        header = set()
        rowSet = self.rowSet

        for index in rowSet:
            data = rowSet[index]
            for item in data:
                header.update(item.__header__.Keys())

        return header

    def getLines(self, header):
        """
        As Indexed row lists have two levels, we'll need to flatten the two into one
        We don't care about the first level indexes for the purpose of datamining anyway
        """
        rowSet = self.rowSet
        data = []
        for index in rowSet:
            data.extend(rowSet[index])

        return data

class CRowSet(RowSetProcessor):
    def getHeader(self):
        return self.rowSet.header.Keys()

    def getLines(self, header):
        return self.rowSet

class CFilterRowSet(CRowSet):
    def getLines(self, header):
        """CFilterRowSet is basicly a dictionary of lists, merge all the lists together"""
        data = []
        for currData in self.rowSet.values():
            data.extend(currData)

        return data

class CIndexedRowSet(CRowSet):
    def getLines(self, header):
        return self.rowSet.values()

class Primitive(RowSetProcessor):
    def getHeader(self):
        """When dealing with a primitive, use a "fake" onerow rowset with just a value"""
        return ['value']

    def getLines(self, header):
        return [{'value': self.rowSet}]

class Skip(RowSetProcessor):
    def getHeader(self):
        print("Skipped {}".format(self.tableName))
        return []

    def getLines(self, header):
        return []

typeMap = {'util.FilterRowset': FilterRowSet,
           'DictLoader': FsdLoader,
           'IndexLoader': FsdLoader,
           'util.IndexedRowLists': IndexedRowLists,
           'dbutil.CRowset': CRowSet,
           'dbutil.CFilterRowset': CFilterRowSet,
           'dbutil.CIndexedRowset': CIndexedRowSet,
           'int': Primitive,
           'unicode': Primitive,
           'dict': Dict,
           'tuple': Skip,
           'util.KeyVal': Skip,} # There's only one call using this one: holoscreenMgr_GetTwoHourCache, its used to return two tables in one. Skipping till I figure out an elegant way to solve that
