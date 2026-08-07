from .decoder import FsdDecoder, FsdPath
from .schema import SchemaReader


class FsdFile(object):

    # Schema is optional: it's either provided as an external file, or embedded into data file
    def __init__(self, data_abspath, schema_abspath=None):
        self._data_abspath = data_abspath
        self._schema_abspath = schema_abspath

    def load(self):
        """Entry point for reading jobs. Returns contents of the file this reader was set up for."""
        with open(self._data_abspath, 'rb') as stream:
            schema, data_offset = SchemaReader(stream, self._schema_abspath, self._data_abspath).load()
            stream.seek(0)
            data = stream.read()
        path = FsdPath('<{}>'.format(self._data_abspath))
        return FsdDecoder(data, schema, path, offset=data_offset).load()
