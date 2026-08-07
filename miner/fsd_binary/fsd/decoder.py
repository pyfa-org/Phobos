import array
import struct
import sys

from .exception import FsdBinaryError, FsdFormatError, FsdSchemaError
from .shared import (
    F32, F64, I32, KEY_OFFSET, KEY_OFFSET_SIZE, U8, U16, U32, U64,
    V2F32, V2F64, V3F32, V3F64, V4F32, V4F64)


class FsdDecoder(object):
    """
    Class, which decodes values out of a buffer with binary FSD data, picking a loader for every
    value according to the type its schema declares.
    """

    def __init__(self, data, schema, path, offset=0):
        self._data = data
        self._schema = schema
        self._path = path
        self._offset = offset

    def load(self):
        # Multi-index dictionaries additionally expose named sub-indexes, but those just re-key
        # records which are already nested in the main index, thus we do not decode them
        if self._schema.get('type') == 'dict' and self._schema.get('buildIndex', False):
            return self._load_index(self._offset, self._schema, self._path)
        return self._route_value(self._offset, self._schema, self._path)

    def _route_value(self, offset, schema, path):
        schema_type = schema.get('type')
        try:
            loader = self._loaders[schema_type]
        except KeyError:
            raise FsdSchemaError('unsupported FSD schema type {!r} at {}'.format(schema_type, path))
        try:
            return loader(self, offset, schema, path)
        except FsdBinaryError:
            raise
        except Exception as e:
            raise FsdFormatError('unable to decode type {!r} at {} offset {}: {}'.format(schema_type, path, offset, e))

    ################################################################################################
    # Primitive reads
    ################################################################################################
    def _check_range(self, offset, size, path):
        length = len(self._data)
        if offset < 0 or size < 0 or offset > length or size > length - offset:
            raise FsdFormatError('read outside {} at offset {} for {} bytes (buffer size {})'.format(path, offset, size, length))

    def _slice_at(self, offset, size, path):
        self._check_range(offset, size, path)
        return self._data[offset:offset + size]

    def _unpack(self, unpacker, offset, path):
        self._check_range(offset, unpacker.size, path)
        try:
            return unpacker.unpack_from(self._data, offset)
        except (struct.error, TypeError, ValueError) as e:
            raise FsdFormatError('unable to unpack {} bytes at {} offset {}: {}'.format(unpacker.size, path, offset, e))

    def _unpack_u32(self, offset, path):
        return self._unpack(U32, offset, path)[0]

    def _decode_str(self, raw, path):
        try:
            return raw.decode('cp1252')
        except UnicodeDecodeError as e:
            raise FsdFormatError('invalid cp1252 string at {}: {}'.format(path, e))

    ################################################################################################
    # Scalar loaders
    ################################################################################################
    def _load_int(self, offset, schema, path):
        unsigned = ('min' in schema and schema['min'] >= 0) or ('exclusiveMin' in schema and schema['exclusiveMin'] >= -1)
        return self._unpack(U32 if unsigned else I32, offset, path)[0]

    def _load_float(self, offset, schema, path):
        unpacker = F64 if schema.get('precision', 'single') == 'double' else F32
        return self._unpack(unpacker, offset, path)[0]

    def _load_bool(self, offset, schema, path):
        return self._unpack(U8, offset, path)[0] == 255

    def _load_string(self, offset, schema, path):
        size = self._unpack_u32(offset, path)
        return self._decode_str(self._slice_at(offset + U32.size, size, path), path)

    def _load_unicode(self, offset, schema, path):
        size = self._unpack_u32(offset, path)
        raw = self._slice_at(offset + U32.size, size, path)
        try:
            return raw.decode('utf-8')
        except UnicodeDecodeError as e:
            raise FsdFormatError('invalid UTF-8 string at {}: {}'.format(path, e))

    def _load_enum(self, offset, schema, path):
        values = schema.get('values', {})
        try:
            max_value = schema['maxEnumValue']
        except KeyError:
            max_value = max(values.values()) if values else 0
        unpacker = U8 if max_value <= 255 else (U16 if max_value <= 65536 else U32)
        value = self._unpack(unpacker, offset, path)[0]
        if schema.get('readEnumValue', False):
            return value
        for name, candidate in values.items():
            if candidate == value:
                return name
        return None

    def _load_vector(self, offset, schema, path):
        double = schema.get('precision', 'single') == 'double'
        values = self._unpack(self._vector_unpackers[(schema['type'], double)], offset, path)
        aliases = schema.get('aliases')
        if aliases:
            return dict((name, values[index]) for name, index in aliases.items())
        return values

    def _load_union(self, offset, schema, path):
        type_index = self._unpack_u32(offset, path)
        options = schema.get('optionTypes', ())
        if type_index >= len(options):
            raise FsdFormatError('union option {} is outside {} choices at {}'.format(type_index, len(options), path))
        option = options[type_index]
        return self._route_value(offset + U32.size, option, path.child('<{}>'.format(option.get('type'))))

    ################################################################################################
    # Composite loaders
    ################################################################################################
    def _load_object(self, offset, schema, path):
        fixed_offsets = schema.get('constantAttributeOffsets', {})
        variable_offsets = {}
        variable_base = None

        if 'size' in schema:
            self._check_range(offset, schema['size'], path)
        else:
            end_of_fixed = schema.get('endOfFixedSizeData', 0)
            self._check_range(offset, end_of_fixed, path)
            optional_lookups = schema.get('optionalValueLookups', {})
            names = schema.get('attributesWithVariableOffsets', ())
            if optional_lookups:
                mask = self._unpack(U64, offset + end_of_fixed, path)[0]
                names = [n for n in names if optional_lookups.get(n) is None or mask & optional_lookups[n]]
            else:
                names = list(names)
            table_start = offset + end_of_fixed + U64.size
            self._check_range(table_start, U32.size * len(names), path)
            variable_base = table_start + U32.size * len(names)
            for index, name in enumerate(names):
                variable_offsets[name] = self._unpack_u32(table_start + index * U32.size, path)

        result = {}
        for name, attribute_schema in schema['attributes'].items():
            child_path = path.child('.{}'.format(name))
            if name in fixed_offsets:
                result[name] = self._route_value(offset + fixed_offsets[name], attribute_schema, child_path)
            elif name in variable_offsets:
                result[name] = self._route_value(variable_base + variable_offsets[name], attribute_schema, child_path)
            elif 'default' in attribute_schema:
                result[name] = attribute_schema['default']
            elif 'isOptional' not in attribute_schema:
                raise FsdFormatError('attribute {!r} is not present at {}'.format(name, path))
        return result

    def _load_list(self, offset, schema, path):
        known_length = schema.get('length')
        if known_length is not None:
            count, count_offset = known_length, 0
        else:
            count, count_offset = self._unpack_u32(offset, path), U32.size
        if count < 0:
            raise FsdFormatError('negative list size at {}'.format(path))

        item_schema = schema['itemTypes']
        result = []
        if 'fixedItemSize' in schema:
            item_size = item_schema.get('size', schema['fixedItemSize'])
            start = offset + count_offset
            self._check_range(start, count * item_size, path)
            for index in range(count):
                result.append(self._route_value(start + item_size * index, item_schema, path.child('[{}]'.format(index))))
        else:
            table_start = offset + count_offset
            self._check_range(table_start, count * U32.size, path)
            for index in range(count):
                relative = self._unpack_u32(table_start + index * U32.size, path)
                result.append(self._route_value(offset + relative, item_schema, path.child('[{}]'.format(index))))
        return tuple(result)

    def _load_dict(self, offset, schema, path):
        size_of_data = self._unpack_u32(offset, path)
        footer_size_offset = offset + size_of_data
        footer_size = self._unpack_u32(footer_size_offset, path)
        if footer_size > size_of_data:
            raise FsdFormatError('dictionary footer at {} exceeds dictionary size'.format(path))
        footer_data = self._slice_at(footer_size_offset - footer_size, footer_size, path)
        result = {}
        for key, item_offset, unused in self._read_footer(footer_data, schema, path):
            result[key] = self._route_value(offset + U32.size + item_offset, schema['valueTypes'], path.child('[{}]'.format(key)))
        return result

    def _load_index(self, offset_to_data, schema, path, offset_to_footer=0):
        object_size = self._unpack_u32(offset_to_data, path)
        footer_size_offset = offset_to_footer - U32.size if offset_to_footer else offset_to_data + object_size
        if footer_size_offset < 0 or footer_size_offset + U32.size > len(self._data):
            raise FsdFormatError('index footer size offset {} is outside {} at {}'.format(footer_size_offset, len(self._data), path))
        footer_size = self._unpack_u32(footer_size_offset, path)
        if footer_size_offset - footer_size < offset_to_data + U32.size:
            raise FsdFormatError('invalid index footer bounds at {}'.format(path))
        footer_data = self._slice_at(footer_size_offset - footer_size, footer_size, path)

        value_schema = schema['valueTypes']
        nested = value_schema.get('buildIndex', False)
        result = {}
        for key, item_offset, item_size in self._read_footer(footer_data, schema, path):
            absolute = offset_to_data + U32.size + item_offset
            child_path = path.child('[{}]'.format(key))
            if nested:
                result[key] = self._load_index(absolute, value_schema, child_path, offset_to_footer=absolute + item_size)
                continue
            if item_size <= 0:
                raise FsdFormatError('indexed item {!r} at {} does not declare a size'.format(key, path))
            self._check_range(absolute, item_size, child_path)
            result[key] = self._route_value(absolute, value_schema, child_path)
        return result

    ################################################################################################
    # Footers
    ################################################################################################
    def _read_footer(self, footer_data, schema, path):
        """Decode dict footer into [(key, offset, size), ...]."""
        footer = FsdDecoder(footer_data, schema['keyFooter'], path.child('<keyFooter>'))
        if schema['keyTypes']['type'] == 'int':
            return footer._load_int_footer()
        return [(i['key'], i['offset'], i.get('size', 0)) for i in footer.load()]

    def _load_int_footer(self):
        sized = 'size' in self._schema['itemTypes']['attributes']
        stride = (KEY_OFFSET_SIZE if sized else KEY_OFFSET).size
        count = self._unpack_u32(0, self._path)
        self._check_range(0, U32.size + count * stride, self._path)
        fields = array.array('i')
        fields.frombytes(self._data[U32.size:U32.size + count * stride])
        if sys.byteorder != 'little':
            fields.byteswap()
        if sized:
            return list(zip(fields[0::3], fields[1::3], fields[2::3]))
        return list(zip(fields[0::2], fields[1::2], [0] * count))

    _vector_unpackers = {
        ('vector2', False): V2F32, ('vector2', True): V2F64,
        ('vector3', False): V3F32, ('vector3', True): V3F64,
        ('vector4', False): V4F32, ('vector4', True): V4F64,
        ('color', False): V4F32, ('color', True): V4F64}

    _loaders = {
        'int': _load_int, 'float': _load_float, 'bool': _load_bool, 'enum': _load_enum,
        'string': _load_string, 'resPath': _load_string, 'unicode': _load_unicode,
        'union': _load_union, 'list': _load_list, 'object': _load_object, 'dict': _load_dict,
        'vector2': _load_vector, 'vector3': _load_vector, 'vector4': _load_vector,
        'color': _load_vector,
        # Field-specific int overrides
        'factionID': _load_int,
        'fsdReference': _load_int,
        'localizationID': _load_int,
        'typeID': _load_int,
        'typeListID': _load_int}


class FsdPath(object):
    """Keep track of current path just for the sake of error reporting."""

    def __init__(self, value, parent=None):
        self.value = value
        self.parent = parent

    def child(self, value):
        return FsdPath(value, self)

    def __str__(self):
        if self.parent is None:
            return self.value
        return '{}{}'.format(self.parent, self.value)
