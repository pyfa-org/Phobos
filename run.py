#!/usr/bin/env python
#===============================================================================
# Copyright (C) 2014-2015 Anton Vorobyov
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

    import reverence

    from flow import FlowManager
    from miner import *
    from translator import Translator
    from writer import *


    parser = argparse.ArgumentParser(description='This script pulls data out of EVE client and writes it in JSON format')
    parser.add_argument('-e', '--eve', help='path to eve folder', required=True)
    parser.add_argument('-r', '--res', help='path to eve shared cache folder', required=True)
    parser.add_argument('-c', '--cache', help='path to eve cache folder', required=True)
    parser.add_argument('-s', '--server', default='tranquility', help='server which was specified in EVE shortcut, defaults to tranquility')
    languages = ('de', 'en-us', 'es', 'fr', 'it', 'ja', 'ru', 'zh', 'multi')
    parser.add_argument('-t', '--translate', default='multi', choices=languages, help='attempt to translate strings into specified language')
    parser.add_argument('-j', '--json', help='output folder for the json files')
    parser.add_argument('-l', '--list', default='', help='comma-separated list of container names to dump')
    args = parser.parse_args()

    # Expand home directory
    path_eve = os.path.expanduser(args.eve)
    path_res = os.path.expanduser(args.res)
    path_cache = os.path.expanduser(args.cache)
    path_json = os.path.expanduser(args.json)

    rvr_language = args.translate if args.translate != 'multi' else 'en-us'
    rvr = reverence.blue.EVE(path_eve, cachepath=path_cache, sharedcachepath=path_res, server=args.server, languageID=rvr_language)

    pickle_miner = ResourcePickleMiner(rvr)
    trans = Translator(pickle_miner)
    bulkdata_miner = BulkdataMiner(rvr, trans)
    staticcache_miner = ResourceStaticCacheMiner(rvr, trans)
    miners = (
        MetadataMiner(path_eve),
        bulkdata_miner,
        staticcache_miner,
        TraitMiner(staticcache_miner, bulkdata_miner, trans),
        SqliteMiner(path_eve, trans),
        CachedCallsMiner(rvr, trans),
        pickle_miner
    )

    writers = (
        JsonWriter(path_json, indent=2),
    )

    FlowManager(miners, writers).run(args.list, args.translate)
