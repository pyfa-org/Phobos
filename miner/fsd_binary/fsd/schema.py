import pickle
from collections import OrderedDict
from io import BytesIO
from os import SEEK_END

from .exception import FsdDependencyError, FsdFormatError, FsdSchemaError
from .shared import U32

MAX_SCHEMA_SIZE = 64 * 1024 * 1024


class SchemaReader(object):

    def __init__(self, stream, schema_abspath, data_abspath):
        self._stream = stream
        self._schema_abspath = schema_abspath
        self._data_abspath = data_abspath

    def load(self):
        # Returns schema & byte stream offset
        if self._schema_abspath is not None:
            return self._load_yaml_schema(), 0
        schema_size = self._get_embedded_size()
        schema_data = self._read_exact_at(U32.size, schema_size, '<embedded schema>')
        return self._load_embedded_schema(schema_data), U32.size + schema_size

    ################################################################################################
    # YAML schema
    ################################################################################################
    def _load_yaml_schema(self):
        try:
            import yaml
        except ImportError:
            raise FsdDependencyError(
                'PyYAML is required to read external FSD .schema files; '
                'install the version listed in requirements.txt')
        try:
            with open(self._schema_abspath, 'rb') as schema_file:
                schema = yaml.safe_load(schema_file.read())
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            raise FsdSchemaError('unable to load FSD schema {}: {}'.format(self._schema_abspath, e))
        return self._validate_schema(schema)

    ################################################################################################
    # Pickled schema
    ################################################################################################
    def _get_embedded_size(self):
        """Size of the schema which is prepended to the data, as declared by the file itself."""
        file_size = self._get_stream_size()
        if file_size < U32.size:
            raise FsdFormatError('{} is too short to contain an FSD schema'.format(self._data_abspath))
        schema_size = self._read_u32_at(0, self._data_abspath)
        if schema_size <= 0 or schema_size > MAX_SCHEMA_SIZE:
            raise FsdSchemaError('invalid embedded schema size {} in {}'.format(schema_size, self._data_abspath))
        if schema_size > file_size - U32.size:
            raise FsdFormatError('embedded schema in {} extends beyond the file'.format(self._data_abspath))
        return schema_size

    def _load_embedded_schema(self, schema_data):
        loader = RestrictedSchemaUnpickler(BytesIO(schema_data), encoding='latin-1')
        try:
            schema = loader.load()
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            raise FsdSchemaError('unable to decode embedded FSD schema: {}'.format(e))
        return self._validate_schema(schema)

    ################################################################################################
    # Validation
    ################################################################################################
    def _validate_schema(self, root):
        """Ensure a decoded schema contains data containers and primitives only."""
        stack = [root]
        seen = set()
        while stack:
            value = stack.pop()
            if isinstance(value, (type(None), bool, int, float, str, bytes)):
                continue
            if not isinstance(value, (dict, OrderedDict, list, tuple)):
                raise FsdSchemaError('unsupported object {} in FSD schema'.format(type(value).__name__))
            # Avoid traversing seen elements, which can happen in case of unpickled schema
            identity = id(value)
            if identity in seen:
                continue
            seen.add(identity)
            if isinstance(value, (dict, OrderedDict)):
                stack.extend(value.keys())
                stack.extend(value.values())
            else:
                stack.extend(value)
        if not isinstance(root, (dict, OrderedDict)):
            raise FsdSchemaError('FSD schema root must be a mapping')
        if 'type' not in root:
            raise FsdSchemaError('FSD schema root does not declare a type')
        return root

    ################################################################################################
    # Stream access
    ################################################################################################
    def _get_stream_size(self):
        current = self._stream.tell()
        self._stream.seek(0, SEEK_END)
        size = self._stream.tell()
        self._stream.seek(current)
        return size

    def _read_u32_at(self, offset, path):
        return U32.unpack(self._read_exact_at(offset, U32.size, path))[0]

    def _read_exact_at(self, offset, size, path):
        if offset < 0 or size < 0:
            raise FsdFormatError('invalid file read at {} offset {} for {} bytes'.format(path, offset, size))
        self._stream.seek(offset)
        data = self._stream.read(size)
        if len(data) != size:
            raise FsdFormatError('short file read at {} offset {}: expected {}, received {}'.format(path, offset, size, len(data)))
        return data


class RestrictedSchemaUnpickler(pickle.Unpickler):
    """
    Denies access to everything in Phobos namespace, except for some whitelisted container types.
    """

    def find_class(self, module, name):
        if module == 'collections' and name == 'OrderedDict':
            return OrderedDict
        raise pickle.UnpicklingError('embedded FSD schema requested forbidden global {}.{}'.format(module, name))
