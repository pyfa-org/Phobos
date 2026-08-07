import re

from util import cachedproperty
from miner.base import BaseMiner
from miner.shared import has_sqlite_header
from .fsd import FsdFile


class FsdBinaryMiner(BaseMiner):
    """Extract schema-driven FSD data from non-SQLite .static files."""

    name = 'fsd_binary'

    def __init__(self, resbrowser, translator):
        self._resbrowser = resbrowser
        self._translator = translator

    def contname_iter(self):
        for container_name in sorted(self._contname_fsdfiles_map):
            yield container_name

    def get_data(self, container_name, language=None, verbose=False, **kwargs):
        try:
            schema_respath, data_respath = self._contname_fsdfiles_map[container_name]
        except KeyError:
            self._container_not_found(container_name)
            return
        data_info = self._resbrowser.get_file_info(data_respath, verify_content=True)
        schema_abspath = None
        if schema_respath is not None:
            schema_abspath = self._resbrowser.get_file_info(schema_respath, verify_content=True).file_abspath
        data = FsdFile(data_info.file_abspath, schema_abspath=schema_abspath).load()
        self._translator.translate_container(data, language, verbose=verbose)
        return data

    @cachedproperty
    def _contname_fsdfiles_map(self):
        """
        Map between container names and locations of FSD schema/data.
        Format: {container name: (fsd schema file path or None, fsd data file path)}
        """
        schemas = {}
        datas = {}
        pattern_schema = re.compile(r'^res:/staticdata/(?P<name>.+)\.schema$', re.UNICODE)
        pattern_data = re.compile(r'^res:/staticdata/(?P<name>.+)\.static$', re.UNICODE)
        for resource_path in self._resbrowser.respath_iter():
            m = pattern_schema.match(resource_path)
            if m:
                schemas[m.group('name').lower()] = resource_path
                continue
            m = pattern_data.match(resource_path)
            if m:
                file_info = self._resbrowser.get_file_info(resource_path, verify_content=False)
                if not has_sqlite_header(file_info.file_abspath):
                    datas[m.group('name').lower()] = resource_path
                continue
        contname_fsdfiles_map = {}
        for container_name, data_respath in datas.iteritems():
            contname_fsdfiles_map[container_name] = (schemas.get(container_name), data_respath)
        return contname_fsdfiles_map
