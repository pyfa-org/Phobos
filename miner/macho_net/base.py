import glob
import os
import os.path
from abc import abstractmethod, abstractproperty

from util import EveNormalizer, cachedproperty
from miner.base import BaseMiner, DiscoveredData, DiscoveryError
from .unmarshal import Unmarshaller


class MachoNetDirError(Exception):
    """Raised when directory with cached data cannot be located."""


class MachoNetBase(BaseMiner):
    """Parts shared across all MachoNet miners."""

    @abstractproperty
    def _cache_dir(self):
        raise NotImplementedError

    @abstractmethod
    def _get_container_name(self, entity_name):
        raise NotImplementedError

    @abstractmethod
    def _get_payload(self, cached_entity):
        raise NotImplementedError

    ################################################################################################
    # Non-abstract
    ################################################################################################
    def __init__(self, path_cache, server_ip, translator):
        self._path_cache = path_cache
        self._server_ip = server_ip
        self._translator = translator

    def discovery_error_iter(self):
        for discovery_error in self._contname_filepath_map.errors:
            yield discovery_error

    def contname_iter(self):
        for container_name in sorted(self._contname_filepath_map.data):
            yield container_name

    def get_data(self, container_name, language=None, verbose=False, **kwargs):
        try:
            file_path = self._contname_filepath_map.data[container_name]
        except KeyError:
            self._container_not_found(container_name)
            return
        unmarshalled_data = self._read_cached_entity_data(file_path)
        normalized_data = EveNormalizer().run(unmarshalled_data)
        self._translator.translate_container(normalized_data, language, verbose=verbose)
        return normalized_data

    @cachedproperty
    def _contname_filepath_map(self):
        """
        Map between container names and absolute paths to them.
        Format: DiscoveredData(data={container name: path to file})
        """
        contname_filepath_map = DiscoveredData(data={})
        if not self._path_cache:
            return contname_filepath_map
        try:
            directory = self._get_cache_dir()
        except (KeyboardInterrupt, SystemExit):
            raise
        # One error in case of being unable to figure what directory to use/how to reach it
        except Exception as e:
            msg = u'unable to locate cached data - {}: {}'.format(type(e).__name__, e)
            contname_filepath_map.errors.append(DiscoveryError(msg))
            return contname_filepath_map
        for file_path in glob.glob(os.path.join(directory, '*.cache')):
            try:
                entity_name = self._read_cached_entity_name(file_path)
                container_name = self._get_container_name(entity_name)
            except (KeyboardInterrupt, SystemExit):
                raise
            # Per-file errors in case of decoding
            except Exception as e:
                msg = u'unable to load cache file {} - {}: {}'.format(os.path.basename(file_path), type(e).__name__, e)
                contname_filepath_map.errors.append(DiscoveryError(msg))
                continue
            contname_filepath_map.data[container_name] = file_path
        return contname_filepath_map

    def _read_cached_entity_name(self, file_path):
        with open(file_path, 'rb') as cache_file:
            file_data = cache_file.read()
        entity_name, _ = Unmarshaller(file_data).load()
        return entity_name

    def _read_cached_entity_data(self, file_path):
        with open(file_path, 'rb') as cache_file:
            file_data = cache_file.read()
        _, cached_entity = Unmarshaller(file_data).load()
        return self._get_payload(cached_entity)

    def _get_cache_dir(self):
        machonet_path = os.path.join(self._path_cache, 'MachoNet')
        server_path = self._get_server_directory(machonet_path)
        return os.path.join(server_path, self._get_protocol_dir(server_path), self._cache_dir)

    def _get_server_directory(self, machonet_path):
        # Use IP address from server info dictionary, or pick a single directory if directory with
        # that name is not found. In case known IP was not found and there are multiple candidates,
        # raise an exception
        if self._server_ip is not None:
            server_path = os.path.join(machonet_path, self._server_ip)
            if os.path.isdir(server_path):
                return server_path
        candidates = self._get_subdirs(machonet_path)
        if len(candidates) != 1:
            infix = '{} or '.format(self._server_ip) if self._server_ip is not None else ''
            found = ', '.join(candidates) if candidates else 'none'
            msg = 'expected cache of {}any single server in {}, but found {}'.format(infix, machonet_path, found)
            raise MachoNetDirError(msg)
        return os.path.join(machonet_path, candidates[0])

    def _get_protocol_dir(self, server_path):
        # Get highest macho net protocol version
        versions = {}
        for name in self._get_subdirs(server_path):
            try:
                versions[int(name)] = name
            except ValueError:
                continue
        if not versions:
            raise MachoNetDirError('no protocol version directory in {}'.format(server_path))
        return versions[max(versions)]

    def _get_subdirs(self, path):
        try:
            names = os.listdir(path)
        except OSError as e:
            raise MachoNetDirError('unable to list {}: {}'.format(path, e))
        return sorted(n for n in names if os.path.isdir(os.path.join(path, n)))
