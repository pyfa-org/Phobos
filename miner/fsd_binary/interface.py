import re

from util import cachedproperty
from miner.base import BaseMiner
from miner.shared import has_sqlite_header
from .decoder import load_fsd_file


class FsdBinaryMiner(BaseMiner):
    """Extract schema-driven FSD data from non-SQLite .static files."""

    name = 'fsd_binary'

    def __init__(self, resbrowser, translator, cache_size=100):
        self._resbrowser = resbrowser
        self._translator = translator
        self._cache_size = cache_size

    def contname_iter(self):
        for container_name in sorted(self._contname_respath_map):
            yield container_name

    def get_data(self, container_name, language=None, verbose=False, **kwargs):
        try:
            data_resource = self._contname_respath_map[container_name]
        except KeyError:
            self._container_not_found(container_name)
            return

        data_info = self._resbrowser.get_file_info(data_resource, verify_content=True)
        schema_resource = self._schemaname_respath_map.get(container_name)
        schema_path = None
        if schema_resource is not None:
            schema_path = self._resbrowser.get_file_info(schema_resource, verify_content=True).file_abspath

        data = load_fsd_file(
            data_info.file_abspath, schema_path=schema_path,
            cache_size=self._cache_size)
        self._translator.translate_container(data, language, verbose=verbose)
        return data

    @cachedproperty
    def _schemaname_respath_map(self):
        schemas = {}
        pattern = re.compile(
            r'^res:/staticdata/(?P<name>.+)\.schema$', re.IGNORECASE)
        for resource_path in self._resbrowser.respath_iter():
            match = pattern.match(resource_path)
            if match:
                schemas[match.group('name').lower()] = resource_path
        return schemas

    @cachedproperty
    def _contname_respath_map(self):
        containers = {}
        pattern = re.compile(
            r'^res:/staticdata/(?P<name>.+)\.static$', re.IGNORECASE)
        for resource_path in self._resbrowser.respath_iter():
            match = pattern.match(resource_path)
            if match is None:
                continue
            file_info = self._resbrowser.get_file_info(resource_path, verify_content=False)
            if has_sqlite_header(file_info.file_abspath):
                continue
            containers[match.group('name').lower()] = resource_path
        return containers
