#!/usr/bin/env python

import sys

from flow import FlowManager
from miner import *
from writer import *
from util import ResourceBrowser, Translator


SERVER_INFO = {'stillness': '13.248.184.148'}


def run(path_eve, server_alias, path_cache, filter_string, language, path_json, group=None):
    resource_browser = ResourceBrowser(eve_path=path_eve, server_alias=server_alias)

    pickle_miner = PickleMiner(resbrowser=resource_browser)
    trans = Translator(pickle_miner=pickle_miner)
    fsdbinary_miner = FsdBinaryMiner(resbrowser=resource_browser, translator=trans)
    fsdbuilt_miner = FsdBuiltMiner(resbrowser=resource_browser, translator=trans)
    fsdlite_miner = FsdLiteMiner(resbrowser=resource_browser, translator=trans)
    metadata_miner = MetadataMiner(resbrowser=resource_browser)
    sqlite_miner = SqliteMiner(resbrowser=resource_browser, translator=trans)
    server_ip = SERVER_INFO[server_alias]
    mn_call_miner = MachoNetCallsMiner(path_cache=path_cache, server_ip=server_ip, translator=trans)
    mn_object_miner = MachoNetObjectsMiner(path_cache=path_cache, server_ip=server_ip, translator=trans)

    miners = [
        metadata_miner,
        fsdbuilt_miner,
        fsdlite_miner,
        fsdbinary_miner,
        sqlite_miner,
        pickle_miner,
        mn_call_miner,
        mn_object_miner]

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
    if major != 3 or minor != 12:
        sys.stderr.write('This application requires Python 3.12 to run, but {0}.{1} was used\n'.format(major, minor))
        sys.exit()

    import argparse
    import os.path

    parser = argparse.ArgumentParser(description='This script extracts data from EVE client and writes it into JSON files')
    parser.add_argument('-e', '--eve', required=True,
                        help="Path to EVE client's directory")
    parser.add_argument('-c', '--cache', default='',
                        help="Path to EVE client's cache directory")
    parser.add_argument('-s', '--server', default='stillness',
                        help='Server to pull data from. Default is "stillness"',
                        choices=('stillness',))
    parser.add_argument('-j', '--json', required=True,
                        help='Output directory for the JSON files')
    parser.add_argument('-t', '--translate', default=None,
                        help='Attempt to translate strings into specified language. Default is no translation',
                        choices=('de', 'en-us', 'es', 'fr', 'it', 'ja', 'ru', 'zh', 'multi'))
    parser.add_argument('-l', '--list', default='',
                        help='Comma-separated list of container names to extract. If not specified, extracts everything')
    parser.add_argument('-g', '--group', type=int, default=None,
                        help='Split output into several files, containing this amount of top-level entities at most')
    args = parser.parse_args()

    # Expand home directory
    path_eve = os.path.expanduser(args.eve)
    path_cache = os.path.expanduser(args.cache)
    path_json = os.path.expanduser(args.json)

    run(path_eve=path_eve, server_alias=args.server, path_cache=path_cache, filter_string=args.list,
        language=args.translate, path_json=path_json, group=args.group)
