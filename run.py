#!/usr/bin/env python
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


import sys

from flow import FlowManager
from miner import *
from writer import *
from util import ResourceBrowser, Translator


def run(path_eve, server_alias, path_cachedcalls, filter_string, language, path_json, group=None):
    resource_browser = ResourceBrowser(eve_path=path_eve, server_alias=server_alias)

    pickle_miner = PickleMiner(resbrowser=resource_browser)
    trans = Translator(pickle_miner=pickle_miner)
    fsdlite_miner = FsdLiteMiner(resbrowser=resource_browser, translator=trans)
    fsdbinary_miner = FsdBinaryMiner(resbrowser=resource_browser, translator=trans)
    miners = [
        MetadataMiner(resbrowser=resource_browser),
        BulkdataMiner(resbrowser=resource_browser, translator=trans),
        fsdlite_miner,
        fsdbinary_miner,
        TraitMiner(fsdlite_miner=fsdlite_miner, fsdbinary_miner=fsdbinary_miner, translator=trans),
        SqliteMiner(resbrowser=resource_browser, translator=trans),
        CachedCallsMiner(path_cachedcalls=path_cachedcalls, translator=trans),
        pickle_miner]

    writers = [
        JsonWriter(path_json, indent=2, group=group)]

    FlowManager(miners, writers).run(filter_string=filter_string, language=language)


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

    import argparse
    import os.path

    parser = argparse.ArgumentParser(description='This script extracts data from EVE client and writes it into JSON files')
    parser.add_argument('-e', '--eve', required=True,
                        help='Path to EVE client\'s folder')
    parser.add_argument('-c', '--calls', default='',
                        help='Path to CachedMethodCalls folder')
    parser.add_argument('-s', '--server', default='tq',
                        help='Server to pull data from. Default is "tq"',
                        choices=('tq', 'sisi', 'duality', 'thunderdome', 'serenity'))
    parser.add_argument('-j', '--json', required=True,
                        help='Output folder for the JSON files')
    parser.add_argument('-t', '--translate', default='multi',
                        help='Attempt to translate strings into specified language. Default is "multi"',
                        choices=('de', 'en-us', 'es', 'fr', 'it', 'ja', 'ru', 'zh', 'multi'))
    parser.add_argument('-l', '--list', default='',
                        help='Comma-separated list of container names to extract. If not specified, extracts everything')
    parser.add_argument('-g', '--group', type=int, default=None,
                        help='Split output into several files, containing this amount of top-level entities at most')
    args = parser.parse_args()

    # Expand home directory
    path_eve = os.path.expanduser(args.eve)
    path_cachedcalls = os.path.expanduser(args.calls)
    path_json = os.path.expanduser(args.json)

    run(path_eve=path_eve, server_alias=args.server, path_cachedcalls=args.calls, filter_string=args.list,
        language=args.translate, path_json=path_json, group=args.group)
