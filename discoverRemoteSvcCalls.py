"""
Remote svc call discovery script, will loop through all cache files and output all service calls it could find a reference to

Copyright (c) 2012 Diego "Sakari" Duclos <sakari@evefit.org>

This code is free software; you can redistribute it and/or modify
it under the terms of the BSD license (see the file LICENSE.txt
included with the distribution).
"""

import argparse
import sys

from reverence import blue

from phobos.helpers.args import getArgs
from phobos.remoteSvc import discover

if __name__ == "__main__":
    try:
        major = sys.version_info.major
        minor = sys.version_info.minor
    except AttributeError:
        major = sys.version_info[0]
        minor = sys.version_info[1]
    if major != 2 or minor < 7:
        sys.stderr.write("This application requires Python 2.7 to run, but {0}.{1} was used\n".format(major, minor))
        sys.exit()

    parser = argparse.ArgumentParser(description="This scripts dumps effects from an sqlite cache dump to mongo")
    parser.add_argument("-e", "--eve", help="path to eve folder", required=True)
    parser.add_argument("-c", "--cache", help="path to eve cache folder", required=True)
    parser.add_argument("-s", "--server", default='tranquility', help="If we're dealing with a singularity cache")
    args = parser.parse_args()

    eve = blue.EVE(args.eve, cachepath=args.cache, server=args.server)

    for service, call in discover(eve):
        print(service, call)
