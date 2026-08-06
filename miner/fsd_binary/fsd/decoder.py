import collections
import mmap
import struct

from .exception import FsdBinaryError, FsdFormatError, FsdSchemaError
from .schema import read_schema_and_offset
from .shared import (
    F32, F64, I32, KEY_OFFSET, KEY_OFFSET_SIZE, U8, U16, U32, U64,
    V2F32, V2F64, V3F32, V3F64, V4F32, V4F64,
    get_stream_size, read_exact_at, read_u32_at)


def load_fsd_file(data_abspath, schema_abspath=None):
    """
    Parse a file in binary FSD format. Schema either has be embedded into file, or path to it has to
    be provided.
    """
    with open(data_abspath, 'rb') as stream:
        schema, data_offset = read_schema_and_offset(stream, schema_abspath, data_abspath)
        return load_with_schema(stream, schema, data_offset, data_abspath)


def load_with_schema(stream, schema, data_offset, data_path):
    cache_size = 100
    path = FsdPath('<{}>'.format(data_path))
    if schema.get('type') == 'dict' and schema.get('buildIndex', False):
        index_class = MultiIndexValue if schema.get('multiIndex', False) else IndexValue
        root = index_class(
            stream, cache_size, schema, path, STATE,
            offset_to_data=data_offset)
        return materialize(root)

    mapping = mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ)
    try:
        root = STATE.represent(mapping, data_offset, schema, path)
        return materialize(root)
    finally:
        mapping.close()


class FsdPath(object):

    def __init__(self, value, parent=None):
        self.value = value
        self.parent = parent

    def child(self, value):
        return FsdPath(value, self)

    def __str__(self):
        if self.parent is None:
            return self.value
        return '{}{}'.format(self.parent, self.value)


def data_length(data):
    try:
        return len(data)
    except TypeError:
        raise FsdFormatError('binary input does not expose a length')


def check_range(data, offset, size, path):
    length = data_length(data)
    if offset < 0 or size < 0 or offset > length or size > length - offset:
        raise FsdFormatError(
            'read outside {} at offset {} for {} bytes (buffer size {})'.format(
                path, offset, size, length))


def unpack(unpacker, data, offset, path):
    check_range(data, offset, unpacker.size, path)
    try:
        return unpacker.unpack_from(data, offset)
    except (struct.error, TypeError, ValueError) as error:
        raise FsdFormatError(
            'unable to unpack {} bytes at {} offset {}: {}'.format(
                unpacker.size, path, offset, error))


def u32(data, offset, path):
    return unpack(U32, data, offset, path)[0]


def slice(data, offset, size, path):
    check_range(data, offset, size, path)
    return data[offset:offset + size]


def decode_cp1252(raw, path):
    try:
        return raw.decode('cp1252')
    except UnicodeDecodeError as error:
        raise FsdFormatError('invalid cp1252 string at {}: {}'.format(path, error))


class VectorValue(object):

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


class LoaderState(object):

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


def load_vector(item_count):
    single_unpackers = {2: V2F32, 3: V3F32, 4: V4F32}
    double_unpackers = {2: V2F64, 3: V3F64, 4: V4F64}

    def load(data, offset, schema, path, state):
        if schema.get('precision', 'single') == 'double':
            unpacker = double_unpackers[item_count]
        else:
            unpacker = single_unpackers[item_count]
        values = unpack(unpacker, data, offset, path)
        if 'aliases' in schema:
            return VectorValue(schema, values)
        return values

    return load


def load_string(data, offset, schema, path, state):
    size = u32(data, offset, path)
    raw = slice(data, offset + U32.size, size, path)
    return decode_cp1252(raw, path)


def load_unicode(data, offset, schema, path, state):
    size = u32(data, offset, path)
    raw = slice(data, offset + U32.size, size, path)
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError as error:
        raise FsdFormatError('invalid UTF-8 string at {}: {}'.format(path, error))


def load_enum(data, offset, schema, path, state):
    try:
        max_value = schema['maxEnumValue']
    except KeyError:
        values = schema.get('values', {})
        max_value = max(values.itervalues()) if values else 0
    if max_value <= 255:
        unpacker = U8
    elif max_value <= 65536:
        unpacker = U16
    else:
        unpacker = U32
    value = unpack(unpacker, data, offset, path)[0]
    if schema.get('readEnumValue', False):
        return value
    for name, candidate in schema.get('values', {}).iteritems():
        if candidate == value:
            return name
    return None


def load_bool(data, offset, schema, path, state):
    return unpack(U8, data, offset, path)[0] == 255


def load_int(data, offset, schema, path, state):
    unsigned = (
        ('min' in schema and schema['min'] >= 0) or
        ('exclusiveMin' in schema and schema['exclusiveMin'] >= -1))
    return unpack(U32 if unsigned else I32, data, offset, path)[0]


def load_float(data, offset, schema, path, state):
    unpacker = F64 if schema.get('precision', 'single') == 'double' else F32
    return unpack(unpacker, data, offset, path)[0]


def load_union(data, offset, schema, path, state):
    type_index = u32(data, offset, path)
    options = schema.get('optionTypes', ())
    if type_index >= len(options):
        raise FsdFormatError(
            'union option {} is outside {} choices at {}'.format(
                type_index, len(options), path))
    option = options[type_index]
    return state.represent(
        data, offset + U32.size, option,
        path.child('<{}>'.format(option.get('type'))))


class FsdObject(object):

    def __init__(self, data, offset, schema, path, state):
        self._data = data
        self._offset = offset
        self._schema = schema
        self._path = path
        self._state = state
        self._variable_offsets = {}
        self._variable_base = None

        if 'size' in schema:
            check_range(data, offset, schema['size'], path)
            return

        end_of_fixed = schema.get('endOfFixedSizeData', 0)
        check_range(data, offset, end_of_fixed, path)
        optional_lookups = schema.get('optionalValueLookups', {})
        variable_attributes = []
        if optional_lookups:
            optional_mask = unpack(
                U64, data, offset + end_of_fixed, path)[0]
            for name in schema.get('attributesWithVariableOffsets', ()):
                mask = optional_lookups.get(name)
                if mask is None or optional_mask & mask:
                    variable_attributes.append(name)
        else:
            variable_attributes = list(
                schema.get('attributesWithVariableOffsets', ()))

        table_start = offset + end_of_fixed + U64.size
        table_size = U32.size * len(variable_attributes)
        check_range(data, table_start, table_size, path)
        self._variable_base = table_start + table_size
        for index, name in enumerate(variable_attributes):
            relative_offset = u32(
                data, table_start + index * U32.size, path)
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
        for name, attribute_schema in self._schema['attributes'].iteritems():
            try:
                yield name, self[name]
            except KeyError:
                if 'isOptional' not in attribute_schema:
                    raise


def load_object(data, offset, schema, path, state):
    return FsdObject(data, offset, schema, path, state)


def load_list(data, offset, schema, path, state, known_length=None):
    known_length = schema.get('length', known_length)
    fixed_length = known_length is not None
    if fixed_length:
        count = known_length
        count_offset = 0
    else:
        count = u32(data, offset, path)
        count_offset = U32.size
    if count < 0:
        raise FsdFormatError('negative list size at {}'.format(path))

    item_schema = schema['itemTypes']
    result = []
    if 'fixedItemSize' in schema:
        item_size = item_schema.get('size', schema['fixedItemSize'])
        start = offset + count_offset
        check_range(data, start, count * item_size, path)
        for index in range(count):
            result.append(state.represent(
                data, start + item_size * index, item_schema,
                path.child('[{}]'.format(index))))
    else:
        table_start = offset + count_offset
        check_range(data, table_start, count * U32.size, path)
        for index in range(count):
            relative_offset = u32(
                data, table_start + index * U32.size, path)
            result.append(state.represent(
                data, offset + relative_offset, item_schema,
                path.child('[{}]'.format(index))))
    return result


class OptimizedFooter(object):

    def __init__(self, data, schema, path):
        attributes = schema['keyFooter']['itemTypes']['attributes']
        self._unpacker = KEY_OFFSET_SIZE if 'size' in attributes else KEY_OFFSET
        self._has_size = self._unpacker is KEY_OFFSET_SIZE
        self._data = data
        self._path = path
        self._count = u32(data, 0, path)
        required = U32.size + self._count * self._unpacker.size
        check_range(data, 0, required, path)

    def _unpack_item(self, index):
        if index < 0 or index >= self._count:
            raise IndexError(index)
        offset = U32.size + index * self._unpacker.size
        values = unpack(self._unpacker, self._data, offset, self._path)
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


class GenericFooter(object):

    def __init__(self, data, schema, path, state):
        self._items = load_list(
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


def create_footer(schema, footer_data, path, state):
    if schema['keyTypes']['type'] == 'int':
        return OptimizedFooter(footer_data, schema, path)
    return GenericFooter(footer_data, schema, path, state)


class MappingValue(object):

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


class DictValue(MappingValue):

    def __init__(self, data, offset, schema, path, state):
        self._data = data
        self._offset = offset
        self._schema = schema
        self._path = path
        self._state = state

        size_of_data = u32(data, offset, path)
        footer_size_offset = offset + size_of_data
        footer_size = u32(data, footer_size_offset, path)
        if footer_size > size_of_data:
            raise FsdFormatError(
                'dictionary footer at {} exceeds dictionary size'.format(path))
        footer_start = footer_size_offset - footer_size
        footer_data = slice(data, footer_start, footer_size, path)
        self._footer = create_footer(schema, footer_data, path, state)

    def _value_at(self, key, relative_offset):
        return self._state.represent(
            self._data, self._offset + U32.size + relative_offset,
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


def load_dict(data, offset, schema, path, state):
    return DictValue(data, offset, schema, path, state)


class IndexValue(MappingValue):

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

        file_size = get_stream_size(stream)
        object_size = read_u32_at(stream, offset_to_data, path)
        footer_size_offset = offset_to_data + object_size
        if offset_to_footer:
            footer_size_offset = offset_to_footer - U32.size
        if footer_size_offset < 0 or footer_size_offset + U32.size > file_size:
            raise FsdFormatError(
                'index footer size offset {} is outside {} at {}'.format(
                    footer_size_offset, file_size, path))
        self._footer_size_offset = footer_size_offset
        self._footer_size = read_u32_at(stream, footer_size_offset, path)
        footer_start = footer_size_offset - self._footer_size
        if footer_start < offset_to_data + U32.size:
            raise FsdFormatError('invalid index footer bounds at {}'.format(path))
        footer_data = read_exact_at(
            stream, footer_start, self._footer_size, path)
        self._footer = create_footer(schema, footer_data, path, state)
        self._object_size = object_size

    def _search(self, key):
        try:
            return self._search_cache[key]
        except KeyError:
            found = self._footer.get(key)
            self._search_cache[key] = found
            return found

    def _value_at(self, key, item_offset, item_size):
        absolute_offset = self._offset_to_data + U32.size + item_offset
        value_schema = self._schema['valueTypes']
        child_path = self._path.child('[{}]'.format(key))
        if value_schema.get('buildIndex', False):
            index_class = (
                MultiIndexValue
                if value_schema.get('multiIndex', False)
                else IndexValue)
            return index_class(
                self._stream, self._cache_size, value_schema, child_path,
                self._state, offset_to_data=absolute_offset,
                offset_to_footer=absolute_offset + item_size)
        if item_size <= 0:
            raise FsdFormatError(
                'indexed item {!r} at {} does not declare a size'.format(
                    key, self._path))
        item_data = read_exact_at(
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


class SubIndexValue(MappingValue):

    def __init__(self, stream, cache_size, footers, schemas,
                 offset_to_data, state, path):
        self._stream = stream
        self._cache_size = cache_size
        self._footers = footers
        self._schemas = schemas
        self._offset_to_data = offset_to_data
        self._state = state
        self._path = path
        # MappingValue expects a footer only for simple mappings.  Sub-index
        # methods below operate over multiple nested footers instead.

    def _value_from_index(self, key, index_id):
        found = self._footers[index_id].get(key)
        if found is None:
            raise KeyError(key)
        item_offset, item_size = found
        value_schema = self._schemas[index_id]['valueTypes']
        absolute_offset = self._offset_to_data + U32.size + item_offset
        child_path = self._path.child('[{}]'.format(key))
        if value_schema.get('buildIndex', False):
            index_class = (
                MultiIndexValue
                if value_schema.get('multiIndex', False)
                else IndexValue)
            return index_class(
                self._stream, self._cache_size, value_schema, child_path,
                self._state, offset_to_data=absolute_offset,
                offset_to_footer=absolute_offset + item_size)
        item_data = read_exact_at(
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
        return sum(len(footer) for footer in self._footers.itervalues())

    def iterkeys(self):
        for footer in self._footers.itervalues():
            for key, unused in footer.iteritems():
                yield key

    def iteritems(self):
        for index_id, footer in self._footers.iteritems():
            for key, unused in footer.iteritems():
                yield key, self._value_from_index(key, index_id)


class MultiIndexValue(IndexValue):

    def __init__(self, stream, cache_size, schema, path, state,
                 offset_to_data=0, offset_to_footer=0):
        IndexValue.__init__(
            self, stream, cache_size, schema, path, state,
            offset_to_data=offset_to_data,
            offset_to_footer=offset_to_footer)
        self._subindexes = {}

        lookup_size_offset = (
            self._footer_size_offset - self._footer_size -
            U32.size)
        lookup_size = read_u32_at(stream, lookup_size_offset, path)
        lookup_start = lookup_size_offset - lookup_size
        lookup_data = read_exact_at(stream, lookup_start, lookup_size, path)
        lookup = state.represent(
            lookup_data, 0, schema['subIndexOffsetLookup'],
            path.child('<MultiIndexAttributes>'))

        nested_footers = {}
        for index_id, offset_info in lookup.iteritems():
            nested_offset = offset_to_data + offset_info['offset']
            nested_size = offset_info['size']
            nested_data = read_exact_at(
                stream, nested_offset, nested_size,
                path.child('<MultiIndexFooter[{}]>'.format(index_id)))
            nested_schema = schema['indexableSchemas'][index_id]
            nested_footers[index_id] = create_footer(
                nested_schema, nested_data, path, state)

        for index_name, index_ids in schema.get('indexNameToIds', {}).iteritems():
            footers = {}
            schemas = {}
            for index_id in index_ids:
                footers[index_id] = nested_footers[index_id]
                schemas[index_id] = schema['indexableSchemas'][index_id]
            self._subindexes[index_name] = SubIndexValue(
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


INTEGER_SCHEMA_TYPES = (
    'int', 'typeID', 'localizationID', 'npcTag', 'deploymentType',
    'npcEnemyFleetTypeID', 'groupBehaviorTreeID', 'npcCorporationID',
    'spawnTableID', 'npcFleetCounterTableID', 'dungeonID', 'typeListID',
    'npcFleetTypeID', 'metaGroupID', 'fsdReference', 'raceID',
    'marketGroupID', 'ShipGroupID', 'certificateTemplateID', 'factionID')

STATE = LoaderState()
STATE.factories.update({
    'float': load_float,
    'vector4': load_vector(4),
    'color': load_vector(4),
    'vector3': load_vector(3),
    'vector2': load_vector(2),
    'string': load_string,
    'resPath': load_string,
    'unicode': load_unicode,
    'enum': load_enum,
    'bool': load_bool,
    'union': load_union,
    'list': load_list,
    'object': load_object,
    'dict': load_dict})
for integer_schema_type in INTEGER_SCHEMA_TYPES:
    STATE.factories[integer_schema_type] = load_int


def materialize(value):
    if value is None or isinstance(value, (bool, int, long, float, unicode)):
        return value
    # On Python 2, binary strings are distinct from unicode.  FSD string
    # loaders normally decode them before this point, but schema defaults may
    # still be byte strings.
    if isinstance(value, bytes):
        return decode_cp1252(value, '<schema default>')
    if isinstance(value, VectorValue):
        aliases = value.schema.get('aliases')
        if aliases:
            result = {}
            for name, index in aliases.iteritems():
                result[materialize(name)] = materialize(value.values[index])
            return result
        return tuple(materialize(item) for item in value.values)
    if isinstance(value, FsdObject):
        result = {}
        for name, item in value.present_items():
            result[materialize(name)] = materialize(item)
        return result
    if isinstance(value, (DictValue, IndexValue, MultiIndexValue, SubIndexValue)):
        result = {}
        for key, item in value.iteritems():
            result[materialize(key)] = materialize(item)
        return result
    if isinstance(value, (dict, collections.OrderedDict)):
        result = {}
        for key, item in value.iteritems():
            result[materialize(key)] = materialize(item)
        return result
    if isinstance(value, (list, tuple)):
        return tuple(materialize(item) for item in value)
    raise FsdFormatError(
        'unable to materialize FSD value of type {}'.format(type(value).__name__))
