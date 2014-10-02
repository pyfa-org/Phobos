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


import glob
import os.path

from reverence import blue

from util import CachedProperty
from .abstract_miner import AbstractMiner
from .eve_normalize import EveNormalizer


class CachedCallsMiner(AbstractMiner):
    """
    Class, responsible for fetching data from EVE client's
    remote service call cache.
    """

    def __init__(self, rvr):
        # Get path to folder with cached method calls
        cache = rvr.getcachemgr()
        self._path_cachedcalls = os.path.join(cache.machocachepath, 'CachedMethodCalls')

    def contname_iter(self):
        for resolved_name in sorted(self._resolved_filepath_map):
            yield resolved_name

    def get_data(self, resolved_name):
        try:
            filepath = self._resolved_filepath_map[resolved_name]
        except KeyError:
            self._container_not_found(resolved_name)
        else:
            _, call_data = self.__read_cache_file(filepath)
            normalized_data = EveNormalizer().run(call_data)
            return normalized_data

    @CachedProperty
    def _resolved_filepath_map(self):
        """
        Access map with cache filenames, keyed against resolved
        call names. If not present, make one.
        Format: {resolved call name: path to source file}
        """
        # Intermediate map between call names and cache files
        # Format: {safe name: [paths to files]}
        safe_filepath_map = {}
        # Cycle through CachedMethodCalls and find all .cache files
        for filepath in glob.glob(os.path.join(self._path_cachedcalls, '*.cache')):
            # In case file cannot be loaded due to any reasons, skip it
            try:
                call_info, _ = self.__read_cache_file(filepath)
            except KeyboardInterrupt:
                raise
            except:
                filename = os.path.basename(filepath)
                print(u'  unable to load cache file {}'.format(filename))
                continue
            # Info has one of 2 following formats:
            # ((service name, service arg1, service arg2, ...), call name, call arg1, call arg2, ...)
            # (service name, call name, call arg1, call arg2, ...)
            # Here we parse info structure according to one of these formats
            svc_info = call_info[0]
            call_info = call_info[1:]
            # Don't forget that we have to secure all name components
            if isinstance(svc_info, (tuple, list)):
                svc_name = self._secure_name(svc_info[0])
                svc_args = svc_info[1:]
            else:
                svc_name = self._secure_name(svc_info)
                svc_args = ()
            call_name = self._secure_name(call_info[0])
            call_args = call_info[1:]
            svc_args_line = u', '.join(self._secure_name(i, arg=True) for i in svc_args)
            call_args_line = u', '.join(self._secure_name(i, arg=True) for i in call_args)
            # Finally, compose full service call in human-readable format and put it into dictionary
            safe_name = u'{}({})_{}({})'.format(svc_name, svc_args_line, call_name, call_args_line)
            filepaths = safe_filepath_map.setdefault(safe_name, [])
            filepaths.append(filepath)
        # Final map which will be exposed
        resolved_filepath_map = {}
        for safe_name, filepaths in safe_filepath_map.items():
            # When we have more than one filepaths, it means that multiple files
            # map onto single safe call name (e.g. single call with argument string
            # passed as unicode or ANSI might result in this), thus we process them
            # differently: solve collisions by appending file name to safe call name
            if len(filepaths) > 1:
                for filepath in filepaths:
                    filename = os.path.splitext(os.path.basename(filepath))[0]
                    resolved_name = u'{}_{}'.format(safe_name, filename)
                    resolved_filepath_map[resolved_name] = filepath
            # If no collisions, just key path against regular safe call name
            else:
                resolved_filepath_map[safe_name] = filepaths[0]
        return resolved_filepath_map

    def __read_cache_file(self, filepath):
        """
        Read & load file located at filepath, and return it as
        tuple with call info and actual cached method result.
        """
        with open(filepath, 'rb') as cachefile:
            filedata = cachefile.read()
        call_info, call_data = blue.marshal.Load(filedata)
        return call_info, call_data['lret']
