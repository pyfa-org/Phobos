import array
import struct
import sys

from .exception import FsdBinaryError, FsdFormatError, FsdSchemaError
from .schema import read_schema_and_offset
from .shared import (
    F32, F64, I32, KEY_OFFSET, KEY_OFFSET_SIZE, U8, U16, U32, U64,
    V2F32, V2F64, V3F32, V3F64, V4F32, V4F64)


def load_fsd_file(data_abspath, schema_abspath=None):
    """
    Parse a file in binary FSD format. Schema either has be embedded into file, or path to it has to
    be provided.
    """
    with open(data_abspath, 'rb') as stream:
        schema, data_offset = read_schema_and_offset(stream, schema_abspath, data_abspath)
        stream.seek(0)
        data = stream.read()
    path = FsdPath('<{}>'.format(data_abspath))
    # Multi-index dictionaries additionally expose named sub-indexes, but those just re-key records
    # which are already nested in the main index, thus we do not decode them
    if schema.get('type') == 'dict' and schema.get('buildIndex', False):
        return load_index(data, data_offset, schema, path)
    return decode(data, data_offset, schema, path)


####################################################################################################
# Primitive reads
####################################################################################################
def check_range(data, offset, size, path):
    length = len(data)
    if offset < 0 or size < 0 or offset > length or size > length - offset:
        raise FsdFormatError('read outside {} at offset {} for {} bytes (buffer size {})'.format(
            path, offset, size, length))


def unpack(unpacker, data, offset, path):
    check_range(data, offset, unpacker.size, path)
    try:
        return unpacker.unpack_from(data, offset)
    except (struct.error, TypeError, ValueError) as e:
        raise FsdFormatError('unable to unpack {} bytes at {} offset {}: {}'.format(unpacker.size, path, offset, e))


def u32(data, offset, path):
    return unpack(U32, data, offset, path)[0]


def slice_at(data, offset, size, path):
    check_range(data, offset, size, path)
    return data[offset:offset + size]


def decode_str(raw, path):
    try:
        return raw.decode('cp1252')
    except UnicodeDecodeError as e:
        raise FsdFormatError('invalid cp1252 string at {}: {}'.format(path, e))


####################################################################################################
# Scalar loaders
####################################################################################################
def load_int(data, offset, schema, path):
    unsigned = ('min' in schema and schema['min'] >= 0) or ('exclusiveMin' in schema and schema['exclusiveMin'] >= -1)
    return unpack(U32 if unsigned else I32, data, offset, path)[0]


def load_float(data, offset, schema, path):
    unpacker = F64 if schema.get('precision', 'single') == 'double' else F32
    return unpack(unpacker, data, offset, path)[0]


def load_bool(data, offset, schema, path):
    return unpack(U8, data, offset, path)[0] == 255


def load_string(data, offset, schema, path):
    size = u32(data, offset, path)
    return decode_str(slice_at(data, offset + U32.size, size, path), path)


def load_unicode(data, offset, schema, path):
    size = u32(data, offset, path)
    raw = slice_at(data, offset + U32.size, size, path)
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError as e:
        raise FsdFormatError('invalid UTF-8 string at {}: {}'.format(path, e))


def load_enum(data, offset, schema, path):
    values = schema.get('values', {})
    try:
        max_value = schema['maxEnumValue']
    except KeyError:
        max_value = max(values.values()) if values else 0
    unpacker = U8 if max_value <= 255 else (U16 if max_value <= 65536 else U32)
    value = unpack(unpacker, data, offset, path)[0]
    if schema.get('readEnumValue', False):
        return value
    for name, candidate in values.items():
        if candidate == value:
            return name
    return None


def load_vector(data, offset, schema, path):
    double = schema.get('precision', 'single') == 'double'
    values = unpack(VECTOR_UNPACKERS[(schema['type'], double)], data, offset, path)
    aliases = schema.get('aliases')
    if aliases:
        return dict((name, values[index]) for name, index in aliases.items())
    return values


def load_union(data, offset, schema, path):
    type_index = u32(data, offset, path)
    options = schema.get('optionTypes', ())
    if type_index >= len(options):
        raise FsdFormatError('union option {} is outside {} choices at {}'.format(
            type_index, len(options), path))
    option = options[type_index]
    return decode(data, offset + U32.size, option, path.child('<{}>'.format(option.get('type'))))


####################################################################################################
# Composite loaders
####################################################################################################
def load_object(data, offset, schema, path):
    fixed_offsets = schema.get('constantAttributeOffsets', {})
    variable_offsets = {}
    variable_base = None

    if 'size' in schema:
        check_range(data, offset, schema['size'], path)
    else:
        end_of_fixed = schema.get('endOfFixedSizeData', 0)
        check_range(data, offset, end_of_fixed, path)
        optional_lookups = schema.get('optionalValueLookups', {})
        names = schema.get('attributesWithVariableOffsets', ())
        if optional_lookups:
            mask = unpack(U64, data, offset + end_of_fixed, path)[0]
            names = [n for n in names if optional_lookups.get(n) is None or mask & optional_lookups[n]]
        else:
            names = list(names)
        table_start = offset + end_of_fixed + U64.size
        check_range(data, table_start, U32.size * len(names), path)
        variable_base = table_start + U32.size * len(names)
        for index, name in enumerate(names):
            variable_offsets[name] = u32(data, table_start + index * U32.size, path)

    result = {}
    for name, attribute_schema in schema['attributes'].items():
        child_path = path.child('.{}'.format(name))
        if name in fixed_offsets:
            result[name] = decode(data, offset + fixed_offsets[name], attribute_schema, child_path)
        elif name in variable_offsets:
            result[name] = decode(
                data, variable_base + variable_offsets[name], attribute_schema, child_path)
        elif 'default' in attribute_schema:
            result[name] = attribute_schema['default']
        elif 'isOptional' not in attribute_schema:
            raise FsdFormatError('attribute {!r} is not present at {}'.format(name, path))
    return result


def load_list(data, offset, schema, path, known_length=None):
    known_length = schema.get('length', known_length)
    if known_length is not None:
        count, count_offset = known_length, 0
    else:
        count, count_offset = u32(data, offset, path), U32.size
    if count < 0:
        raise FsdFormatError('negative list size at {}'.format(path))

    item_schema = schema['itemTypes']
    result = []
    if 'fixedItemSize' in schema:
        item_size = item_schema.get('size', schema['fixedItemSize'])
        start = offset + count_offset
        check_range(data, start, count * item_size, path)
        for index in range(count):
            result.append(decode(data, start + item_size * index, item_schema, path.child('[{}]'.format(index))))
    else:
        table_start = offset + count_offset
        check_range(data, table_start, count * U32.size, path)
        for index in range(count):
            relative = u32(data, table_start + index * U32.size, path)
            result.append(decode(data, offset + relative, item_schema, path.child('[{}]'.format(index))))
    return tuple(result)


def read_footer(footer_data, schema, path):
    """Decode dict footer into [(key, offset, size), ...]."""
    if schema['keyTypes']['type'] != 'int':
        entries = []
        for item in load_list(footer_data, 0, schema['keyFooter'], path.child('<keyFooter>')):
            entries.append((item['key'], item['offset'], item.get('size', 0)))
        return entries
    sized = 'size' in schema['keyFooter']['itemTypes']['attributes']
    stride = (KEY_OFFSET_SIZE if sized else KEY_OFFSET).size
    count = u32(footer_data, 0, path)
    check_range(footer_data, 0, U32.size + count * stride, path)
    fields = array.array('i')
    fields.frombytes(footer_data[U32.size:U32.size + count * stride])
    if sys.byteorder != 'little':
        fields.byteswap()
    if sized:
        return list(zip(fields[0::3], fields[1::3], fields[2::3]))
    return list(zip(fields[0::2], fields[1::2], [0] * count))


def load_dict(data, offset, schema, path):
    size_of_data = u32(data, offset, path)
    footer_size_offset = offset + size_of_data
    footer_size = u32(data, footer_size_offset, path)
    if footer_size > size_of_data:
        raise FsdFormatError('dictionary footer at {} exceeds dictionary size'.format(path))
    footer_data = slice_at(data, footer_size_offset - footer_size, footer_size, path)
    result = {}
    for key, item_offset, unused in read_footer(footer_data, schema, path):
        result[key] = decode(data, offset + U32.size + item_offset, schema['valueTypes'], path.child('[{}]'.format(key)))
    return result


def load_index(data, offset_to_data, schema, path, offset_to_footer=0):
    object_size = u32(data, offset_to_data, path)
    footer_size_offset = (offset_to_footer - U32.size if offset_to_footer
                          else offset_to_data + object_size)
    if footer_size_offset < 0 or footer_size_offset + U32.size > len(data):
        raise FsdFormatError('index footer size offset {} is outside {} at {}'.format(footer_size_offset, len(data), path))
    footer_size = u32(data, footer_size_offset, path)
    if footer_size_offset - footer_size < offset_to_data + U32.size:
        raise FsdFormatError('invalid index footer bounds at {}'.format(path))
    footer_data = slice_at(data, footer_size_offset - footer_size, footer_size, path)

    value_schema = schema['valueTypes']
    nested = value_schema.get('buildIndex', False)
    result = {}
    for key, item_offset, item_size in read_footer(footer_data, schema, path):
        absolute = offset_to_data + U32.size + item_offset
        child_path = path.child('[{}]'.format(key))
        if nested:
            result[key] = load_index(data, absolute, value_schema, child_path, offset_to_footer=absolute + item_size)
            continue
        if item_size <= 0:
            raise FsdFormatError('indexed item {!r} at {} does not declare a size'.format(key, path))
        check_range(data, absolute, item_size, child_path)
        result[key] = decode(data, absolute, value_schema, child_path)
    return result


####################################################################################################
# Dispatch
####################################################################################################
def decode(data, offset, schema, path):
    schema_type = schema.get('type')
    try:
        loader = LOADERS[schema_type]
    except KeyError:
        raise FsdSchemaError('unsupported FSD schema type {!r} at {}'.format(schema_type, path))
    try:
        return loader(data, offset, schema, path)
    except FsdBinaryError:
        raise
    except Exception as e:
        raise FsdFormatError('unable to decode type {!r} at {} offset {}: {}'.format(schema_type, path, offset, e))

VECTOR_UNPACKERS = {
    ('vector2', False): V2F32, ('vector2', True): V2F64,
    ('vector3', False): V3F32, ('vector3', True): V3F64,
    ('vector4', False): V4F32, ('vector4', True): V4F64,
    ('color', False): V4F32, ('color', True): V4F64}

LOADERS = {
    'int': load_int, 'float': load_float, 'bool': load_bool, 'enum': load_enum,
    'string': load_string, 'resPath': load_string, 'unicode': load_unicode,
    'union': load_union, 'list': load_list, 'object': load_object, 'dict': load_dict,
    'vector2': load_vector, 'vector3': load_vector, 'vector4': load_vector, 'color': load_vector,
    # Field-specific int overrides
    'factionID': load_int,
    'fsdReference': load_int,
    'localizationID': load_int,
    'typeID': load_int,
    'typeListID': load_int}


####################################################################################################
# Error reporting
####################################################################################################
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
