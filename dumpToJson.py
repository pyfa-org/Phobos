#===============================================================================
# Copyright (C) 2012 Diego Duclos
# Copyright (c) 2012 Romain "Artefact2" Dalmaso <artefact2@gmail.com>
# Copyright (C) 2013 Anton Vorobyov
#
# This code is free software; you can redistribute it and/or modify
# it under the terms of the BSD license (see the file LICENSE.txt
# included with the distribution).
#===============================================================================


"""Cache dumper script, uses phobos to dump a json dump to disk"""


import argparse
import os.path
import re
import sqlite3
import sys
from ConfigParser import ConfigParser
from datetime import datetime
from time import mktime

from reverence import blue

from phobos.writer.jsonWriter import JsonWriter
from phobos.remoteSvc import discover as discoverSvc
from phobos.rowSetProcessor import RowSetProcessor


if __name__ == '__main__':
    try:
        major = sys.version_info.major
        minor = sys.version_info.minor
    except AttributeError:
        major = sys.version_info[0]
        minor = sys.version_info[1]
    if major != 2 or minor < 7:
        sys.stderr.write('This application requires Python 2.7 to run, but {0}.{1} was used\n'.format(major, minor))
        sys.exit()

    parser = argparse.ArgumentParser(description='This scripts dumps effects from an sqlite cache dump to mongo')
    parser.add_argument('-e', '--eve', help='path to eve folder', required=True)
    parser.add_argument('-c', '--cache', help='path to eve cache folder', required=True)
    parser.add_argument('-s', '--server', default='tranquility', help='server which was specified in EVE shortcut, defaults to tranquility')
    parser.add_argument('-j', '--json', help='output folder for the json files')
    parser.add_argument('-t', '--tables', help='|-separated list of table names to dump (all tables are dumped by default)')
    parser.add_argument('-l', '--language', help='Which language to dump in. Suggested values: de, ru, en-us, ja, zh, fr, it, es', default='en-us')
    args = parser.parse_args()

    # Needed args & helpers
    evePath = os.path.expanduser(args.eve)
    cachePath = os.path.expanduser(args.cache)
    jsonPath = os.path.expanduser(args.json)

    eve = blue.EVE(evePath, cachepath=cachePath, server=args.server, languageID=args.language)
    cfg = eve.getconfigmgr()

    # Helper function
    def processRowSet(tableName, rowSet):
        print('processing {}'.format(tableName))
        header, lines = RowSetProcessor(tableName, rowSet, cfg).run()
        JsonWriter(tableName, header, lines, jsonPath, indent=4).run()

    def processMetadata():
        tableName = 'metadata'
        print('processing {}'.format(tableName))
        # Read client version
        header = ['fieldName', 'fieldValue']
        lines = []
        try:
            config = ConfigParser()
            config.read(os.path.join(evePath, 'start.ini'))
            eveVersion = config.getint('main', 'build')
        except:
            print('failed to detect client version')
            eveVersion = None
        lines.append({'fieldName': 'clientBuild', 'fieldValue': eveVersion})
        # Generate UNIX-style timestamp of current UTC time
        timestamp = int(mktime(datetime.utcnow().timetuple()))
        lines.append({'fieldName': 'dumpTime', 'fieldValue': timestamp})
        JsonWriter(tableName, header, lines, jsonPath, indent=4).run()

    # If -t is present, only dump the specified tables
    if(args.tables != None):

        def getArg(argString):
            argString = argString.strip()
            if argString == 'None':
                return None
            try:
                numFloat = float(argString)
                numInt = int(argString)
            except ValueError:
                return argString
            else:
                if '.' not in argString and numFloat == numInt:
                    return numInt
                else:
                    return numFloat

        for tableName in args.tables.split('|'):
            try:
                match = re.match('(?P<svcName>[^\(\)]+)\((?P<svcArgs>[^\(\)]*)\)_(?P<callName>[^\(\)]+)\((?P<callArgs>[^\(\)]*)\)', tableName)
                if match:
                    svcName = str(match.group('svcName'))
                    svcArgsString = match.group('svcArgs')
                    if len(svcArgsString) > 0:
                        svcArgs = tuple(getArg(argString) for argString in svcArgsString.split(','))
                    else:
                        svcArgs = ()
                    callName = str(match.group('callName'))
                    callArgsString = match.group('callArgs')
                    if len(callArgsString) > 0:
                        callArgs = tuple(getArg(argString) for argString in callArgsString.split(','))
                    else:
                        callArgs = ()
                    if len(svcArgs) > 0:
                        service = (svcName, tuple(svcArgs))
                    else:
                        service = svcName
                    rowSet = getattr(eve.RemoteSvc(service), callName)(*callArgs)
                else:
                    rowSet = getattr(cfg, tableName)
                processRowSet(tableName, rowSet)
            except KeyboardInterrupt:
                raise
            except:
                print('failed to process {}'.format(tableName))
    else:
        # Process bulkdata tables
        for tableName in cfg.tables:
            try:
                rowSet = getattr(cfg, tableName)
                processRowSet(tableName, rowSet)
            except KeyboardInterrupt:
                raise
            except:
                print('failed to process {}'.format(tableName))

        # Process remote service calls
        for serviceName, serviceArgs, callName, callArgs in discoverSvc(eve):
            try:
                tableName = u'{}({})_{}({})'.format(
                    serviceName,
                    ', '.join(unicode(arg) for arg in serviceArgs),
                    callName,
                    ', '.join(unicode(arg) for arg in callArgs)
                )
                if len(serviceArgs) > 0:
                    service = (serviceName, serviceArgs)
                else:
                    service = serviceName
                rowSet = getattr(eve.RemoteSvc(service), callName)(*callArgs)
                processRowSet(tableName, rowSet)
            except KeyboardInterrupt:
                raise
            except:
                print('failed to process {}'.format(tableName))

        # Process SQLite from bulkdata folder
        bulkSqlitePath = os.path.join(evePath, 'bulkdata', 'mapbulk.db')
        conn = sqlite3.connect(bulkSqlitePath, detect_types=sqlite3.PARSE_COLNAMES | sqlite3.PARSE_DECLTYPES)
        # Go through master table to detect real tables
        for masterRow in conn.execute('SELECT * FROM sqlite_master WHERE type = "table"'):
            tableName = masterRow[1]
            rowSet = []
            # Gather column names
            columnNames = []
            for columnData in conn.execute(u'PRAGMA table_info({0})'.format(tableName)):
                columnNames.append(columnData[1])
            columnRange = range(len(columnNames))
            statement = u"SELECT {0} FROM {1}".format(u", ".join(columnNames), tableName)
            for row in conn.execute(statement):
                dictRow = dict((columnNames[i], row[i]) for i in columnRange)
                rowSet.append(dictRow)
            processRowSet(tableName, rowSet)
        conn.close()

    processMetadata()

    print('all done')
