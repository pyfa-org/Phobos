#===============================================================================
# Copyright (C) 2012 Diego Duclos
# Copyright (C) 2013 Anton Vorobyov
#
# This code is free software; you can redistribute it and/or modify
# it under the terms of the BSD license (see the file LICENSE.txt
# included with the distribution).
#===============================================================================


import json
import os
from collections import OrderedDict

import reverence


class StubbingEncoder(json.JSONEncoder):
    """
    Objects which cannot be serialized are replaced with stub
    """

    def default(self, o):
        if isinstance(o, reverence.fsd.FSD_Dict):
            return dict(o)
        if isinstance(o, reverence.fsd._FixedSizeList):
            return tuple(o)
        if isinstance(o, reverence.fsd.FSD_Object):
            new = {}
            for attrName in o.attributes:
                new[attrName] = getattr(o, attrName, None)
            return new
        if isinstance(o, reverence.fsd.FSD_NamedVector):
            vector = OrderedDict()
            aliasData = o.schema['aliases']
            for alias in sorted(aliasData, key=aliasData.get):
                index = aliasData[alias]
                vector[alias] = o.data[index]
            return vector
        return 'unserializable class {}'.format(type(o))


class JsonWriter:
    """Json writer, takes input from the rowSetProcessor and writes it out to json files in the given folder, one file per table"""
    def __init__(self, tableName, header, lines, folder, indent=None):
        self.tableName = tableName
        self.header = header
        self.lines = lines
        self.folder = folder
        self.indent = indent

    def run(self):
        dataList = []
        header = self.header

        # Data in the lines isn't always in primitive format
        # It might be wrapped in various classes that implement dict like interfaces
        # Dump it all in a "real" dict so json doesn't complain
        for line in self.lines:
            try:
                dataList.append({k: line[k] for k in header})
            except:
                print(line)
                raise
        if not os.path.exists(self.folder):
            os.makedirs(self.folder, mode=0o755)
        json.dump(
            dataList,
            open(os.path.join(self.folder, '{}.json'.format(self.tableName)), 'w'),
            cls=StubbingEncoder,
            indent=self.indent,
            encoding='cp1252'
        )
