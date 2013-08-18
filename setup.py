#===============================================================================
# Copyright (C) 2012 Diego Duclos
# Copyright (C) 2013 Anton Vorobyov
#
# This code is free software; you can redistribute it and/or modify
# it under the terms of the BSD license (see the file LICENSE.txt
# included with the distribution).
#===============================================================================


import distutils
from distutils.core import setup
from distutils.core import Extension

import platform
import sys
import os

try:
    os.chdir(os.path.dirname(sys.argv[0]))
except OSError:
    pass

if sys.version_info < (2, 6) or sys.version_info > (2, 8):
    raise RuntimeError("Python 2.6 or 2.7 required")

desc = """
Phobos is a cache dumper for the eve online cache, it uses reverence to dump all cache files it can find to json.
"""


setup(
    name = "phobos",

    url = "http://jira.dev.evefit.org/browse/PHOBOS",

    version = "0.1",

    description = "EVE online cache dumper",

    long_description = desc,

    classifiers = [
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 2 :: Only",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Database",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
    ],

    license = "MIT",
    author = 'Diego "Sakari" Duclos',
    author_email = "sakari@evefit.org",

    packages = ["phobos", "phobos.writer"],
    package_dir = {"phobos": "phobos"},
)


