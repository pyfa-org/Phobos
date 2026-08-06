"""Reader for the schema-driven FSD format stored in ``.static`` files.

This module is intentionally self-contained.  In particular, it does not open
or import EVE's ``code.ccp`` archive.  The similar-looking ``.fsdbinary`` files
which are paired with native ``.pyd`` loaders belong to :mod:`miner.fsd_built`
and are outside this miner's scope.

Two schema arrangements are supported:

* an optimized schema embedded as a length-prefixed Python 2 pickle; and
* an optimized YAML schema in a sibling ``.schema`` resource.

The binary layouts implemented below mirror the runtime readers in
``fsd.schemas.binaryLoader`` from EVE build 3396210.
"""


import collections
import io
import mmap
import os
import pickle
import re
import struct

from util import cachedproperty
from .base import BaseMiner
from .shared import has_sqlite_header


_U8 = struct.Struct('<B')
_U16 = struct.Struct('<H')
_U32 = struct.Struct('<I')
_I32 = struct.Struct('<i')
_U64 = struct.Struct('<Q')
_F32 = struct.Struct('<f')
_F64 = struct.Struct('<d')
_V2F = struct.Struct('<ff')
_V2D = struct.Struct('<dd')
_V3F = struct.Struct('<fff')
_V3D = struct.Struct('<ddd')
_V4F = struct.Struct('<ffff')
_V4D = struct.Struct('<dddd')
_KEY_OFFSET = struct.Struct('<ii')
_KEY_OFFSET_SIZE = struct.Struct('<iii')

_MAX_SCHEMA_SIZE = 64 * 1024 * 1024


class FsdBinaryError(Exception):
    """Base exception for schema-driven FSD parsing errors."""


class FsdFormatError(FsdBinaryError):
    """Raised when an FSD file is truncated or contains invalid offsets."""


class FsdSchemaError(FsdBinaryError):
    """Raised when an embedded or external schema cannot be used safely."""


class FsdDependencyError(FsdBinaryError):
    """Raised when support for an external schema dependency is unavailable."""


class _FsdPath(object):

    def __init__(self, value, parent=None):
        self.value = value
        self.parent = parent

    def child(self, value):
        return _FsdPath(value, self)

    def __str__(self):
        if self.parent is None:
            return self.value
        return '{}{}'.format(self.parent, self.value)


def _data_length(data):
    try:
        return len(data)
    except TypeError:
        raise FsdFormatError('binary input does not expose a length')


def _check_range(data, offset, size, path):
    length = _data_length(data)
    if offset < 0 or size < 0 or offset > length or size > length - offset:
        raise FsdFormatError(
            'read outside {} at offset {} for {} bytes (buffer size {})'.format(
                path, offset, size, length))


def _unpack(unpacker, data, offset, path):
    _check_range(data, offset, unpacker.size, path)
    try:
        return unpacker.unpack_from(data, offset)
    except (struct.error, TypeError, ValueError) as error:
        raise FsdFormatError(
            'unable to unpack {} bytes at {} offset {}: {}'.format(
                unpacker.size, path, offset, error))


def _u32(data, offset, path):
    return _unpack(_U32, data, offset, path)[0]


def _slice(data, offset, size, path):
    _check_range(data, offset, size, path)
    return data[offset:offset + size]


def _read_exact_at(stream, offset, size, path):
    if offset < 0 or size < 0:
        raise FsdFormatError(
            'invalid file read at {} offset {} for {} bytes'.format(path, offset, size))
    stream.seek(offset)
    data = stream.read(size)
    if len(data) != size:
        raise FsdFormatError(
            'short file read at {} offset {}: expected {}, received {}'.format(
                path, offset, size, len(data)))
    return data


def _read_u32_at(stream, offset, path):
    return _U32.unpack(_read_exact_at(stream, offset, _U32.size, path))[0]


def _stream_size(stream):
    current = stream.tell()
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(current)
    return size


class _RestrictedSchemaUnpickler(pickle.Unpickler):

    def find_class(self, module, name):
        if module == 'collections' and name == 'OrderedDict':
            return collections.OrderedDict
        raise pickle.UnpicklingError(
            'embedded FSD schema requested forbidden global {}.{}'.format(module, name))

    # Python 2's pure-Python pickle implementation uses find_global.
    find_global = find_class


def _validate_schema_graph(root):
    """Ensure a decoded schema contains data containers and primitives only."""
    primitive_types = (type(None), bool, int, long, float, str, unicode)
    containers = (dict, collections.OrderedDict, list, tuple)
    stack = [root]
    seen = set()
    while stack:
        value = stack.pop()
        if isinstance(value, primitive_types):
            continue
        if not isinstance(value, containers):
            raise FsdSchemaError(
                'unsupported object {} in FSD schema'.format(type(value).__name__))
        identity = id(value)
        if identity in seen:
            continue
        seen.add(identity)
        if isinstance(value, (dict, collections.OrderedDict)):
            stack.extend(value.keys())
            stack.extend(value.values())
        else:
            stack.extend(value)
    if not isinstance(root, (dict, collections.OrderedDict)):
        raise FsdSchemaError('FSD schema root must be a mapping')
    if 'type' not in root:
        raise FsdSchemaError('FSD schema root does not declare a type')
    return root


def _load_embedded_schema(raw_schema):
    stream = io.BytesIO(raw_schema)
    try:
        try:
            loader = _RestrictedSchemaUnpickler(stream, encoding='latin-1')
        except TypeError:  # Python 2 Unpickler has no encoding argument
            stream.seek(0)
            loader = _RestrictedSchemaUnpickler(stream)
        schema = loader.load()
    except FsdSchemaError:
        raise
    except Exception as error:
        raise FsdSchemaError('unable to decode embedded FSD schema: {}'.format(error))
    return _validate_schema_graph(schema)


def _load_yaml_schema(schema_path):
    try:
        import yaml
    except ImportError:
        raise FsdDependencyError(
            'PyYAML is required to read external FSD .schema files; '
            'install the version listed in requirements.txt')
    try:
        with open(schema_path, 'rb') as schema_file:
            schema = yaml.safe_load(schema_file.read())
    except FsdBinaryError:
        raise
    except Exception as error:
        raise FsdSchemaError(
            'unable to load FSD schema {}: {}'.format(schema_path, error))
    return _validate_schema_graph(schema)


def _decode_cp1252(raw, path):
    try:
        return raw.decode('cp1252')
    except UnicodeDecodeError as error:
        raise FsdFormatError('invalid cp1252 string at {}: {}'.format(path, error))


class _VectorValue(object):

    def __init__(self, schema, values):
        self.schema = schema
        self.values = values

    def __getitem__(self, key):
        aliases = self.schema.get('aliases', {})
        if key in aliases:
            key = aliases[key]
        return self.values[key]

    def __getattr__(self, name):
        try:
            return self[name]
        except (IndexError, KeyError) as error:
            raise AttributeError(str(error))


class _LoaderState(object):

    def __init__(self):
        self.factories = {}

    def represent(self, data, offset, schema, path):
        schema_type = schema.get('type')
        try:
            factory = self.factories[schema_type]
        except KeyError:
            raise FsdSchemaError(
                "unsupported FSD schema type {!r} at {}".format(schema_type, path))
        try:
            return factory(data, offset, schema, path, self)
        except FsdBinaryError:
            raise
        except Exception as error:
            raise FsdFormatError(
                "unable to decode type {!r} at {} offset {}: {}".format(
                    schema_type, path, offset, error))


def _load_vector(item_count):
    single_unpackers = {2: _V2F, 3: _V3F, 4: _V4F}
    double_unpackers = {2: _V2D, 3: _V3D, 4: _V4D}

    def load(data, offset, schema, path, state):
        if schema.get('precision', 'single') == 'double':
            unpacker = double_unpackers[item_count]
        else:
            unpacker = single_unpackers[item_count]
        values = _unpack(unpacker, data, offset, path)
        if 'aliases' in schema:
            return _VectorValue(schema, values)
        return values

    return load


def _load_string(data, offset, schema, path, state):
    size = _u32(data, offset, path)
    raw = _slice(data, offset + _U32.size, size, path)
    return _decode_cp1252(raw, path)


def _load_unicode(data, offset, schema, path, state):
    size = _u32(data, offset, path)
    raw = _slice(data, offset + _U32.size, size, path)
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError as error:
        raise FsdFormatError('invalid UTF-8 string at {}: {}'.format(path, error))


def _load_enum(data, offset, schema, path, state):
    try:
        max_value = schema['maxEnumValue']
    except KeyError:
        values = schema.get('values', {})
        max_value = max(values.values()) if values else 0
    if max_value <= 255:
        unpacker = _U8
    elif max_value <= 65536:
        unpacker = _U16
    else:
        unpacker = _U32
    value = _unpack(unpacker, data, offset, path)[0]
    if schema.get('readEnumValue', False):
        return value
    for name, candidate in schema.get('values', {}).items():
        if candidate == value:
            return name
    return None


def _load_bool(data, offset, schema, path, state):
    return _unpack(_U8, data, offset, path)[0] == 255


def _load_int(data, offset, schema, path, state):
    unsigned = (
        ('min' in schema and schema['min'] >= 0) or
        ('exclusiveMin' in schema and schema['exclusiveMin'] >= -1))
    return _unpack(_U32 if unsigned else _I32, data, offset, path)[0]


def _load_float(data, offset, schema, path, state):
    unpacker = _F64 if schema.get('precision', 'single') == 'double' else _F32
    return _unpack(unpacker, data, offset, path)[0]


def _load_union(data, offset, schema, path, state):
    type_index = _u32(data, offset, path)
    options = schema.get('optionTypes', ())
    if type_index >= len(options):
        raise FsdFormatError(
            'union option {} is outside {} choices at {}'.format(
                type_index, len(options), path))
    option = options[type_index]
    return state.represent(
        data, offset + _U32.size, option,
        path.child('<{}>'.format(option.get('type'))))


class _FsdObject(object):

    def __init__(self, data, offset, schema, path, state):
        self._data = data
        self._offset = offset
        self._schema = schema
        self._path = path
        self._state = state
        self._variable_offsets = {}
        self._variable_base = None

        if 'size' in schema:
            _check_range(data, offset, schema['size'], path)
            return

        end_of_fixed = schema.get('endOfFixedSizeData', 0)
        _check_range(data, offset, end_of_fixed, path)
        optional_lookups = schema.get('optionalValueLookups', {})
        variable_attributes = []
        if optional_lookups:
            optional_mask = _unpack(
                _U64, data, offset + end_of_fixed, path)[0]
            for name in schema.get('attributesWithVariableOffsets', ()):
                mask = optional_lookups.get(name)
                if mask is None or optional_mask & mask:
                    variable_attributes.append(name)
        else:
            variable_attributes = list(
                schema.get('attributesWithVariableOffsets', ()))

        table_start = offset + end_of_fixed + _U64.size
        table_size = _U32.size * len(variable_attributes)
        _check_range(data, table_start, table_size, path)
        self._variable_base = table_start + table_size
        for index, name in enumerate(variable_attributes):
            relative_offset = _u32(
                data, table_start + index * _U32.size, path)
            self._variable_offsets[name] = relative_offset

    def __getitem__(self, name):
        try:
            attribute_schema = self._schema['attributes'][name]
        except KeyError:
            raise KeyError(
                "attribute {!r} is not declared at {}".format(name, self._path))
        child_path = self._path.child('.{}'.format(name))
        fixed_offsets = self._schema.get('constantAttributeOffsets', {})
        if name in fixed_offsets:
            return self._state.represent(
                self._data, self._offset + fixed_offsets[name],
                attribute_schema, child_path)
        if name not in self._variable_offsets:
            if 'default' in attribute_schema:
                return attribute_schema['default']
            raise KeyError(
                "attribute {!r} is not present at {}".format(name, self._path))
        return self._state.represent(
            self._data,
            self._variable_base + self._variable_offsets[name],
            attribute_schema,
            child_path)

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(str(error))

    def present_items(self):
        for name, attribute_schema in self._schema['attributes'].items():
            try:
                yield name, self[name]
            except KeyError:
                if 'isOptional' not in attribute_schema:
                    raise


def _load_object(data, offset, schema, path, state):
    return _FsdObject(data, offset, schema, path, state)


def _load_list(data, offset, schema, path, state, known_length=None):
    known_length = schema.get('length', known_length)
    fixed_length = known_length is not None
    if fixed_length:
        count = known_length
        count_offset = 0
    else:
        count = _u32(data, offset, path)
        count_offset = _U32.size
    if count < 0:
        raise FsdFormatError('negative list size at {}'.format(path))

    item_schema = schema['itemTypes']
    result = []
    if 'fixedItemSize' in schema:
        item_size = item_schema.get('size', schema['fixedItemSize'])
        start = offset + count_offset
        _check_range(data, start, count * item_size, path)
        for index in range(count):
            result.append(state.represent(
                data, start + item_size * index, item_schema,
                path.child('[{}]'.format(index))))
    else:
        table_start = offset + count_offset
        _check_range(data, table_start, count * _U32.size, path)
        for index in range(count):
            relative_offset = _u32(
                data, table_start + index * _U32.size, path)
            result.append(state.represent(
                data, offset + relative_offset, item_schema,
                path.child('[{}]'.format(index))))
    return result


class _OptimizedFooter(object):

    def __init__(self, data, schema, path):
        attributes = schema['keyFooter']['itemTypes']['attributes']
        self._unpacker = _KEY_OFFSET_SIZE if 'size' in attributes else _KEY_OFFSET
        self._has_size = self._unpacker is _KEY_OFFSET_SIZE
        self._data = data
        self._path = path
        self._count = _u32(data, 0, path)
        required = _U32.size + self._count * self._unpacker.size
        _check_range(data, 0, required, path)

    def _unpack_item(self, index):
        if index < 0 or index >= self._count:
            raise IndexError(index)
        offset = _U32.size + index * self._unpacker.size
        values = _unpack(self._unpacker, self._data, offset, self._path)
        if self._has_size:
            return values
        return values[0], values[1], 0

    def get(self, key):
        low = 0
        high = self._count - 1
        while low <= high:
            middle = (low + high) // 2
            current_key, offset, size = self._unpack_item(middle)
            if current_key < key:
                low = middle + 1
            elif current_key > key:
                high = middle - 1
            else:
                return offset, size
        return None

    def iteritems(self):
        for index in range(self._count):
            key, offset, size = self._unpack_item(index)
            yield key, (offset, size)

    def __len__(self):
        return self._count


class _GenericFooter(object):

    def __init__(self, data, schema, path, state):
        self._items = _load_list(
            data, 0, schema['keyFooter'], path.child('<keyFooter>'), state)

    def get(self, key):
        low = 0
        high = len(self._items) - 1
        while low <= high:
            middle = (low + high) // 2
            item = self._items[middle]
            current_key = item['key']
            if current_key < key:
                low = middle + 1
            elif current_key > key:
                high = middle - 1
            else:
                try:
                    size = item['size']
                except KeyError:
                    size = 0
                return item['offset'], size
        return None

    def iteritems(self):
        for item in self._items:
            try:
                size = item['size']
            except KeyError:
                size = 0
            yield item['key'], (item['offset'], size)

    def __len__(self):
        return len(self._items)


def _create_footer(schema, footer_data, path, state):
    if schema['keyTypes']['type'] == 'int':
        return _OptimizedFooter(footer_data, schema, path)
    return _GenericFooter(footer_data, schema, path, state)


class _MappingValue(object):

    def iterkeys(self):
        for key, unused in self._footer.iteritems():
            yield key

    def __iter__(self):
        return self.iterkeys()

    def __len__(self):
        return len(self._footer)

    def __contains__(self, key):
        try:
            return self._footer.get(key) is not None
        except TypeError:
            return False

    def get(self, key, default=None):
        try:
            return self[key]
        except (KeyError, IndexError, TypeError):
            return default

    def keys(self):
        return list(self.iterkeys())

    def values(self):
        return [value for unused, value in self.iteritems()]

    def items(self):
        return list(self.iteritems())


class _DictValue(_MappingValue):

    def __init__(self, data, offset, schema, path, state):
        self._data = data
        self._offset = offset
        self._schema = schema
        self._path = path
        self._state = state

        size_of_data = _u32(data, offset, path)
        footer_size_offset = offset + size_of_data
        footer_size = _u32(data, footer_size_offset, path)
        if footer_size > size_of_data:
            raise FsdFormatError(
                'dictionary footer at {} exceeds dictionary size'.format(path))
        footer_start = footer_size_offset - footer_size
        footer_data = _slice(data, footer_start, footer_size, path)
        self._footer = _create_footer(schema, footer_data, path, state)

    def _value_at(self, key, relative_offset):
        return self._state.represent(
            self._data, self._offset + _U32.size + relative_offset,
            self._schema['valueTypes'],
            self._path.child('[{}]'.format(key)))

    def __getitem__(self, key):
        found = self._footer.get(key)
        if found is None:
            raise KeyError('key {!r} not found at {}'.format(key, self._path))
        return self._value_at(key, found[0])

    def iteritems(self):
        for key, offset_and_size in self._footer.iteritems():
            yield key, self._value_at(key, offset_and_size[0])


def _load_dict(data, offset, schema, path, state):
    return _DictValue(data, offset, schema, path, state)


class _IndexValue(_MappingValue):

    def __init__(self, stream, cache_size, schema, path, state,
                 offset_to_data=0, offset_to_footer=0):
        self._stream = stream
        self._cache_size = max(0, cache_size)
        self._schema = schema
        self._path = path
        self._state = state
        self._offset_to_data = offset_to_data
        self._cache = collections.OrderedDict()
        self._search_cache = {}

        file_size = _stream_size(stream)
        object_size = _read_u32_at(stream, offset_to_data, path)
        footer_size_offset = offset_to_data + object_size
        if offset_to_footer:
            footer_size_offset = offset_to_footer - _U32.size
        if footer_size_offset < 0 or footer_size_offset + _U32.size > file_size:
            raise FsdFormatError(
                'index footer size offset {} is outside {} at {}'.format(
                    footer_size_offset, file_size, path))
        self._footer_size_offset = footer_size_offset
        self._footer_size = _read_u32_at(stream, footer_size_offset, path)
        footer_start = footer_size_offset - self._footer_size
        if footer_start < offset_to_data + _U32.size:
            raise FsdFormatError('invalid index footer bounds at {}'.format(path))
        footer_data = _read_exact_at(
            stream, footer_start, self._footer_size, path)
        self._footer = _create_footer(schema, footer_data, path, state)
        self._object_size = object_size

    def _search(self, key):
        try:
            return self._search_cache[key]
        except KeyError:
            found = self._footer.get(key)
            self._search_cache[key] = found
            return found

    def _value_at(self, key, item_offset, item_size):
        absolute_offset = self._offset_to_data + _U32.size + item_offset
        value_schema = self._schema['valueTypes']
        child_path = self._path.child('[{}]'.format(key))
        if value_schema.get('buildIndex', False):
            index_class = (
                _MultiIndexValue
                if value_schema.get('multiIndex', False)
                else _IndexValue)
            return index_class(
                self._stream, self._cache_size, value_schema, child_path,
                self._state, offset_to_data=absolute_offset,
                offset_to_footer=absolute_offset + item_size)
        if item_size <= 0:
            raise FsdFormatError(
                'indexed item {!r} at {} does not declare a size'.format(
                    key, self._path))
        item_data = _read_exact_at(
            self._stream, absolute_offset, item_size, child_path)
        return self._state.represent(item_data, 0, value_schema, child_path)

    def __getitem__(self, key):
        if key in self._cache:
            value = self._cache.pop(key)
            self._cache[key] = value
            return value
        found = self._search(key)
        if found is None:
            raise KeyError('key {!r} not found at {}'.format(key, self._path))
        value = self._value_at(key, found[0], found[1])
        if self._cache_size:
            if len(self._cache) >= self._cache_size:
                self._cache.popitem(last=False)
            self._cache[key] = value
        return value

    def iteritems(self):
        for key, offset_and_size in self._footer.iteritems():
            yield key, self._value_at(
                key, offset_and_size[0], offset_and_size[1])


class _SubIndexValue(_MappingValue):

    def __init__(self, stream, cache_size, footers, schemas,
                 offset_to_data, state, path):
        self._stream = stream
        self._cache_size = cache_size
        self._footers = footers
        self._schemas = schemas
        self._offset_to_data = offset_to_data
        self._state = state
        self._path = path
        # _MappingValue expects a footer only for simple mappings.  Sub-index
        # methods below operate over multiple nested footers instead.

    def _value_from_index(self, key, index_id):
        found = self._footers[index_id].get(key)
        if found is None:
            raise KeyError(key)
        item_offset, item_size = found
        value_schema = self._schemas[index_id]['valueTypes']
        absolute_offset = self._offset_to_data + _U32.size + item_offset
        child_path = self._path.child('[{}]'.format(key))
        if value_schema.get('buildIndex', False):
            index_class = (
                _MultiIndexValue
                if value_schema.get('multiIndex', False)
                else _IndexValue)
            return index_class(
                self._stream, self._cache_size, value_schema, child_path,
                self._state, offset_to_data=absolute_offset,
                offset_to_footer=absolute_offset + item_size)
        item_data = _read_exact_at(
            self._stream, absolute_offset, item_size, child_path)
        return self._state.represent(item_data, 0, value_schema, child_path)

    def __getitem__(self, key):
        for index_id in self._footers:
            try:
                return self._value_from_index(key, index_id)
            except KeyError:
                pass
        raise KeyError('key {!r} not found at {}'.format(key, self._path))

    def __contains__(self, key):
        try:
            self[key]
            return True
        except KeyError:
            return False

    def __len__(self):
        return sum(len(footer) for footer in self._footers.values())

    def iterkeys(self):
        for footer in self._footers.values():
            for key, unused in footer.iteritems():
                yield key

    def iteritems(self):
        for index_id, footer in self._footers.items():
            for key, unused in footer.iteritems():
                yield key, self._value_from_index(key, index_id)


class _MultiIndexValue(_IndexValue):

    def __init__(self, stream, cache_size, schema, path, state,
                 offset_to_data=0, offset_to_footer=0):
        _IndexValue.__init__(
            self, stream, cache_size, schema, path, state,
            offset_to_data=offset_to_data,
            offset_to_footer=offset_to_footer)
        self._subindexes = {}

        lookup_size_offset = (
            self._footer_size_offset - self._footer_size -
            _U32.size)
        lookup_size = _read_u32_at(stream, lookup_size_offset, path)
        lookup_start = lookup_size_offset - lookup_size
        lookup_data = _read_exact_at(stream, lookup_start, lookup_size, path)
        lookup = state.represent(
            lookup_data, 0, schema['subIndexOffsetLookup'],
            path.child('<MultiIndexAttributes>'))

        nested_footers = {}
        for index_id, offset_info in lookup.iteritems():
            nested_offset = offset_to_data + offset_info['offset']
            nested_size = offset_info['size']
            nested_data = _read_exact_at(
                stream, nested_offset, nested_size,
                path.child('<MultiIndexFooter[{}]>'.format(index_id)))
            nested_schema = schema['indexableSchemas'][index_id]
            nested_footers[index_id] = _create_footer(
                nested_schema, nested_data, path, state)

        for index_name, index_ids in schema.get('indexNameToIds', {}).items():
            footers = {}
            schemas = {}
            for index_id in index_ids:
                footers[index_id] = nested_footers[index_id]
                schemas[index_id] = schema['indexableSchemas'][index_id]
            self._subindexes[index_name] = _SubIndexValue(
                stream, cache_size, footers, schemas, offset_to_data,
                state, path.child('<MultiIndexAttributes>.{}'.format(index_name)))

    def __getattr__(self, name):
        try:
            subindexes = object.__getattribute__(self, '_subindexes')
        except AttributeError:
            raise AttributeError(name)
        if name in subindexes:
            return subindexes[name]
        raise AttributeError(
            "multi-index dictionary has no index named {!r}".format(name))


_INTEGER_SCHEMA_TYPES = (
    'int', 'typeID', 'localizationID', 'npcTag', 'deploymentType',
    'npcEnemyFleetTypeID', 'groupBehaviorTreeID', 'npcCorporationID',
    'spawnTableID', 'npcFleetCounterTableID', 'dungeonID', 'typeListID',
    'npcFleetTypeID', 'metaGroupID', 'fsdReference', 'raceID',
    'marketGroupID', 'ShipGroupID', 'certificateTemplateID', 'factionID')

_STATE = _LoaderState()
_STATE.factories.update({
    'float': _load_float,
    'vector4': _load_vector(4),
    'color': _load_vector(4),
    'vector3': _load_vector(3),
    'vector2': _load_vector(2),
    'string': _load_string,
    'resPath': _load_string,
    'unicode': _load_unicode,
    'enum': _load_enum,
    'bool': _load_bool,
    'union': _load_union,
    'list': _load_list,
    'object': _load_object,
    'dict': _load_dict})
for _integer_schema_type in _INTEGER_SCHEMA_TYPES:
    _STATE.factories[_integer_schema_type] = _load_int


def _materialize(value):
    if value is None or isinstance(value, (bool, int, long, float, unicode)):
        return value
    # On Python 2, binary strings are distinct from unicode.  FSD string
    # loaders normally decode them before this point, but schema defaults may
    # still be byte strings.
    if isinstance(value, bytes):
        return _decode_cp1252(value, '<schema default>')
    if isinstance(value, _VectorValue):
        aliases = value.schema.get('aliases')
        if aliases:
            result = {}
            for name, index in aliases.items():
                result[_materialize(name)] = _materialize(value.values[index])
            return result
        return tuple(_materialize(item) for item in value.values)
    if isinstance(value, _FsdObject):
        result = {}
        for name, item in value.present_items():
            result[_materialize(name)] = _materialize(item)
        return result
    if isinstance(value, (_DictValue, _IndexValue, _MultiIndexValue, _SubIndexValue)):
        result = {}
        for key, item in value.iteritems():
            result[_materialize(key)] = _materialize(item)
        return result
    if isinstance(value, (dict, collections.OrderedDict)):
        result = {}
        for key, item in value.items():
            result[_materialize(key)] = _materialize(item)
        return result
    if isinstance(value, (list, tuple)):
        return tuple(_materialize(item) for item in value)
    raise FsdFormatError(
        'unable to materialize FSD value of type {}'.format(type(value).__name__))


def _read_schema_and_offset(stream, schema_path, data_path):
    if schema_path is not None:
        return _load_yaml_schema(schema_path), 0

    file_size = _stream_size(stream)
    if file_size < _U32.size:
        raise FsdFormatError('{} is too short to contain an FSD schema'.format(data_path))
    schema_size = _read_u32_at(stream, 0, data_path)
    if schema_size <= 0 or schema_size > _MAX_SCHEMA_SIZE:
        raise FsdSchemaError(
            'invalid embedded schema size {} in {}'.format(schema_size, data_path))
    if schema_size > file_size - _U32.size:
        raise FsdFormatError(
            'embedded schema in {} extends beyond the file'.format(data_path))
    raw_schema = _read_exact_at(
        stream, _U32.size, schema_size, '<embedded schema>')
    return _load_embedded_schema(raw_schema), _U32.size + schema_size


def _load_with_schema(stream, schema, data_offset, data_path, cache_size):
    path = _FsdPath('<{}>'.format(data_path))
    if schema.get('type') == 'dict' and schema.get('buildIndex', False):
        index_class = _MultiIndexValue if schema.get('multiIndex', False) else _IndexValue
        root = index_class(
            stream, cache_size, schema, path, _STATE,
            offset_to_data=data_offset)
        return _materialize(root)

    mapping = mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ)
    try:
        root = _STATE.represent(mapping, data_offset, schema, path)
        return _materialize(root)
    finally:
        mapping.close()


def load_fsd_file(data_path, schema_path=None, cache_size=100):
    """Parse one FSD ``.static`` file into Python built-in values.

    ``schema_path`` should name an already optimized YAML schema.  If it is
    omitted, the optimized schema is read from the data file's prefix.
    """
    if cache_size is None:
        cache_size = 100
    if cache_size < 0:
        raise ValueError('cache_size must not be negative')
    with open(data_path, 'rb') as stream:
        schema, data_offset = _read_schema_and_offset(
            stream, schema_path, data_path)
        return _load_with_schema(
            stream, schema, data_offset, data_path, cache_size)


class FsdBinaryMiner(BaseMiner):
    """Extract schema-driven FSD data from non-SQLite ``.static`` files."""

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
