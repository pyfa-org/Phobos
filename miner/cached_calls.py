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


import glob
import os.path

from reverence import blue

from util import EveNormalizer, cachedproperty
from .base import BaseMiner


class CachedCallsMiner(BaseMiner):
    """
    Class, responsible for fetching data from EVE client's
    remote service call cache.
    """

    name = 'cached_calls'

    def __init__(self, path_cachedcalls, translator):
        self._path_cachedcalls = path_cachedcalls
        self._translator = translator

    def contname_iter(self):
        for container_name in sorted(self._contname_filepath_map):
            yield container_name

    def get_data(self, container_name, language=None, verbose=False, **kwargs):
        try:
            filepath = self._contname_filepath_map[container_name]
        except KeyError:
            self._container_not_found(container_name)
        else:
            _, call_data = self.__read_cache_file(filepath)
            normalized_data = EveNormalizer().run(call_data)
            self._translator.translate_container(normalized_data, language, verbose=verbose)
            return normalized_data

    @cachedproperty
    def _contname_filepath_map(self):
        """
        Make map with cache filenames, keyed against formatted call names.
        Format: {container name: path to file}
        """
        contname_filepath_map = {}
        # Path might be not specified, in this case do not do anything
        if self._path_cachedcalls:
            # Cycle through CachedMethodCalls and find all .cache files
            for file_path in glob.glob(os.path.join(self._path_cachedcalls, '*.cache')):
                # In case file cannot be loaded due to any reasons, skip it
                try:
                    call_info, _ = self.__read_cache_file(file_path)
                except KeyboardInterrupt:
                    raise
                except:
                    file_name = os.path.basename(file_path)
                    print(u'  unable to load cache file {}'.format(file_name))
                    continue
                # Info has one of 2 following formats:
                # - ((service name, service arg1, service arg2, ...), call name, call arg1, call arg2, ...)
                # - (service name, call name, call arg1, call arg2, ...)
                # Here we parse info structure according to one of these formats
                svc_info = call_info[0]
                call_info = call_info[1:]
                if isinstance(svc_info, (tuple, list)):
                    svc_name = svc_info[0]
                    svc_args = svc_info[1:]
                else:
                    svc_name = svc_info
                    svc_args = ()
                call_name = call_info[0]
                call_args = call_info[1:]
                svc_args_line = u', '.join(unicode(a) for a in svc_args)
                call_args_line = u', '.join(unicode(a) for a in call_args)
                # Finally, compose full service call in human-readable format and put it into dictionary
                container_name = u'{}({})_{}({})'.format(svc_name, svc_args_line, call_name, call_args_line)
                contname_filepath_map[container_name] = file_path
        return contname_filepath_map

    def __read_cache_file(self, filepath):
        """
        Read & load file located at filepath, and return it as
        tuple with call info and actual cached method result.
        """
        with open(filepath, 'rb') as cachefile:
            filedata = cachefile.read()
        cached_call_info, cached_call_data = blue.marshal.Load(filedata)
        return cached_call_info, cached_call_data['lret']
