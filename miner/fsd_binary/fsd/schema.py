"""
Two schema arrangements are supported:

* an optimized schema embedded as a length-prefixed Python 2 pickle
* an optimized YAML schema in a sibling .schema resource
"""

import pickle
from collections import OrderedDict
from io import BytesIO

from .exception import FsdDependencyError, FsdFormatError, FsdSchemaError
from .shared import U32, get_stream_size, read_exact_at, read_u32_at

MAX_SCHEMA_SIZE = 64 * 1024 * 1024


def read_schema_and_offset(stream, schema_path, data_path):
    # Schema in separate file
    if schema_path is not None:
        return load_yaml_schema(schema_path), 0
    # Embedded schema
    file_size = get_stream_size(stream)
    if file_size < U32.size:
        raise FsdFormatError('{} is too short to contain an FSD schema'.format(data_path))
    schema_size = read_u32_at(stream, 0, data_path)
    if schema_size <= 0 or schema_size > MAX_SCHEMA_SIZE:
        raise FsdSchemaError('invalid embedded schema size {} in {}'.format(schema_size, data_path))
    if schema_size > file_size - U32.size:
        raise FsdFormatError('embedded schema in {} extends beyond the file'.format(data_path))
    schema_data = read_exact_at(stream, U32.size, schema_size, '<embedded schema>')
    return load_embedded_schema(schema_data), U32.size + schema_size


def load_yaml_schema(schema_path):
    try:
        import yaml
    except ImportError:
        raise FsdDependencyError(
            'PyYAML is required to read external FSD .schema files; '
            'install the version listed in requirements.txt')
    try:
        with open(schema_path, 'rb') as schema_file:
            schema = yaml.safe_load(schema_file.read())
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        raise FsdSchemaError('unable to load FSD schema {}: {}'.format(schema_path, e))
    return validate_schema_graph(schema)


class RestrictedSchemaUnpickler(pickle.Unpickler):

    def find_class(self, module, name):
        if module == 'collections' and name == 'OrderedDict':
            return OrderedDict
        raise pickle.UnpicklingError('embedded FSD schema requested forbidden global {}.{}'.format(module, name))


def load_embedded_schema(schema_data):
    stream = BytesIO(schema_data)
    loader = RestrictedSchemaUnpickler(stream)
    try:
        schema = loader.load()
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        raise FsdSchemaError('unable to decode embedded FSD schema: {}'.format(e))
    return validate_schema_graph(schema)


def validate_schema_graph(root):
    """Ensure a decoded schema contains data containers and primitives only."""
    primitive_types = (type(None), bool, int, long, float, str, unicode)
    containers = (dict, OrderedDict, list, tuple)
    stack = [root]
    seen = set()
    while stack:
        value = stack.pop()
        if isinstance(value, primitive_types):
            continue
        if not isinstance(value, containers):
            raise FsdSchemaError('unsupported object {} in FSD schema'.format(type(value).__name__))
        # Avoid traversing seen elements, which can happen in case of unpickled schema
        identity = id(value)
        if identity in seen:
            continue
        seen.add(identity)
        if isinstance(value, (dict, OrderedDict)):
            stack.extend(value.iterkeys())
            stack.extend(value.itervalues())
        else:
            stack.extend(value)
    if not isinstance(root, (dict, OrderedDict)):
        raise FsdSchemaError('FSD schema root must be a mapping')
    if 'type' not in root:
        raise FsdSchemaError('FSD schema root does not declare a type')
    return root
