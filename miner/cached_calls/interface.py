import glob
import os.path

from util import EveNormalizer, cachedproperty
from miner.base import BaseMiner
from .unmarshal import MarshalError, Unmarshaller


class CachedCallsMiner(BaseMiner):
    """Class, responsible for fetching data from EVE client's remote service call cache."""

    name = 'cached_calls'

    def __init__(self, path_cachedcalls, translator):
        self._path_cachedcalls = path_cachedcalls
        self._translator = translator

    def contname_iter(self):
        for container_name in sorted(self._contname_filepath_map):
            yield container_name

    def get_data(self, container_name, language=None, verbose=False, **kwargs):
        try:
            file_path = self._contname_filepath_map[container_name]
        except KeyError:
            self._container_not_found(container_name)
            return
        unused, call_data = self.__read_cache_file(file_path)
        data = EveNormalizer().run(call_data)
        self._translator.translate_container(data, language, verbose=verbose)
        return data

    @cachedproperty
    def _contname_filepath_map(self):
        """
        Make map with cache filenames, keyed against formatted call names.
        Format: {container name: path to file}
        """
        contname_filepath_map = {}
        # Path is optional, when it is not specified there is nothing to extract
        if not self._path_cachedcalls:
            return contname_filepath_map
        for file_path in glob.glob(os.path.join(self._path_cachedcalls, '*.cache')):
            try:
                call_info, unused = self.__read_cache_file(file_path)
                container_name = self.__get_container_name(call_info)
            except (KeyboardInterrupt, SystemExit):
                raise
            # Cache files are written by the client at its own discretion, thus a file we cannot
            # read is not a reason to fail the rest of them
            except Exception as e:
                print(u'  unable to load cache file {} - {}: {}'.format(os.path.basename(file_path), type(e).__name__, e))
                continue
            contname_filepath_map[container_name] = file_path
        return contname_filepath_map

    def __get_container_name(self, call_info):
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
        return u'{}({})_{}({})'.format(svc_name, svc_args_line, call_name, call_args_line)

    def __read_cache_file(self, file_path):
        """
        Read & load file located at file path, and return it as tuple with call info and actual
        cached method result.
        """
        with open(file_path, 'rb') as cache_file:
            file_data = cache_file.read()
        call_info, call_data = Unmarshaller(file_data).load()
        try:
            return call_info, call_data['lret']
        except (TypeError, KeyError):
            raise MarshalError('cached call result does not carry a return value')
