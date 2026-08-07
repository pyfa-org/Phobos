"""
Format is reimplemented after Marshal.cpp from the blue library
(https://github.com/carbonengine/blue).
"""

import struct
import zlib
from enum import IntEnum, unique

from .dbrow import RowDescriptor
from .exception import MarshalError, UnsupportedTypeError
from .strings import STRINGS


SHARED_FLAG = 0x40
TYPE_MASK = 0x3f

U32 = struct.Struct('<I')
I8 = struct.Struct('<b')
I16 = struct.Struct('<h')
I32 = struct.Struct('<i')
I64 = struct.Struct('<q')
F64 = struct.Struct('<d')


@unique
class Type(IntEnum):
    """Type tags, as defined in the blue's marshal source."""
    NONE = 1
    GLOBAL = 2
    INT64 = 3
    INT32 = 4
    INT16 = 5
    INT8 = 6
    INT_N1 = 7
    INT_0 = 8
    INT_1 = 9
    FLOAT = 10
    FLOAT_0 = 11
    COMPLEX = 12
    STR = 13
    STR_EMPTY = 14
    STR_CHAR = 15
    STR_SHORT = 16
    STR_TABLE = 17
    UNICODE = 18
    BUFFER = 19
    TUPLE = 20
    LIST = 21
    DICT = 22
    INSTANCE = 23
    CALLBACK = 25
    PICKLE = 26
    REFERENCE = 27
    CRC_CHECK = 28
    TRUE = 31
    FALSE = 32
    PICKLER = 33
    REDUCE = 34
    NEWOBJ = 35
    TUPLE0 = 36
    TUPLE1 = 37
    LIST0 = 38
    LIST1 = 39
    UNICODE_0 = 40
    UNICODE_1 = 41
    DBROW = 42
    WSTREAM = 43
    TUPLE2 = 44
    MARK = 45
    UTF8_OBSOLETE = 46
    LONG = 47
    SIGNATURE = 126
    SIGNATURE2 = 125


class Unmarshaller:
    """
    Class, which reads objects out of marshal data, picking a reader for every object according
    to the type tag which precedes it.
    """

    def __init__(self, data):
        self._data = data
        self._stream = None

    def load(self):
        """Entry point for reading jobs. Returns the single object passed data carries."""
        # Stream is set up here rather than on instantiation, so that the same data can be read
        # more than once
        self._stream = Stream(self._data)
        self._read_header()
        return self._route_object()

    def _route_object(self):
        """Pick proper method for the object stream is at, and invoke it."""
        tag = ord(self._stream.read(1))
        type_id = tag & TYPE_MASK
        # Objects referred to more than once are flagged, so that they are registered when read
        is_shared = bool(tag & SHARED_FLAG)
        try:
            method = self._readers[type_id]
        except KeyError:
            raise UnsupportedTypeError('unsupported marshal type {} at offset {}'.format(type_id, self._stream.pos - 1))
        return method(self, is_shared)

    def _read_header(self):
        stream = self._stream
        signature = ord(stream.read(1))
        if signature not in (Type.SIGNATURE, Type.SIGNATURE2):
            raise MarshalError('data does not start with a marshal signature (got {})'.format(signature))
        if signature == Type.SIGNATURE2:
            raise UnsupportedTypeError('versioned marshal streams are not supported')
        map_count = stream.unpack(I32)
        if map_count < 0:
            raise MarshalError('invalid shared object count {} in header'.format(map_count))
        if map_count:
            # Mapping table sits at the very end of the data, and is not part of the body
            table_size = map_count * U32.size
            if table_size > stream.end - stream.pos:
                raise MarshalError('shared object table does not fit into the stream')
            stream.end -= table_size
            table = stream.data[stream.end:stream.end + table_size]
            stream.mapping = [I32.unpack(table[i:i + 4])[0] for i in range(0, table_size, 4)]
            for number in stream.mapping:
                if not 1 <= number <= map_count:
                    raise MarshalError('bogus shared object mapping entry {}'.format(number))
        stream.shared = [None] * map_count

    ################################################################################################
    # Scalars
    ################################################################################################
    def _read_none(self, is_shared):
        return None

    def _read_true(self, is_shared):
        return True

    def _read_false(self, is_shared):
        return False

    def _read_int64(self, is_shared):
        return self._stream.unpack(I64)

    def _read_int32(self, is_shared):
        return self._stream.unpack(I32)

    def _read_int16(self, is_shared):
        return self._stream.unpack(I16)

    def _read_int8(self, is_shared):
        return self._stream.unpack(I8)

    def _read_int_n1(self, is_shared):
        return -1

    def _read_int_0(self, is_shared):
        return 0

    def _read_int_1(self, is_shared):
        return 1

    def _read_float(self, is_shared):
        return self._stream.unpack(F64)

    def _read_float_0(self, is_shared):
        return 0.0

    def _read_long(self, is_shared):
        raw = self._stream.read(self._stream.read_length())
        if not raw:
            return 0
        value = 0
        for i, byte in enumerate(raw):
            value |= byte << (8 * i)
        # Stored as a signed little-endian integer of arbitrary width
        if raw[-1] & 0x80:
            value -= 1 << (8 * len(raw))
        if is_shared:
            self._stream.mark_shared(value)
        return value

    ################################################################################################
    # Strings
    ################################################################################################
    def _read_str(self, is_shared):
        return self._stream.read(self._stream.read_length())

    def _read_str_empty(self, is_shared):
        return b''

    def _read_str_char(self, is_shared):
        return self._stream.read(1)

    def _read_str_short(self, is_shared):
        return self._stream.read(ord(self._stream.read(1)))

    def _read_str_table(self, is_shared):
        index = ord(self._stream.read(1))
        if not 1 <= index <= len(STRINGS):
            raise MarshalError('invalid string table index {}'.format(index))
        return STRINGS[index - 1]


    def _read_unicode(self, is_shared):
        # LE UCS-2 for eveo
        return self._stream.read(self._stream.read_length() * 2).decode('utf-16-le')

    def _read_unicode_0(self, is_shared):
        return u''

    def _read_unicode_1(self, is_shared):
        # LE UCS-2 for eveo
        return self._stream.read(2).decode('utf-16-le')

    def _read_utf8(self, is_shared):
        return self._stream.read(self._stream.read_length()).decode('utf-8')

    def _read_buffer(self, is_shared):
        data = self._stream.read(self._stream.read_length())
        if is_shared:
            self._stream.mark_shared(data)
        return data

    ################################################################################################
    # Containers
    ################################################################################################
    def _read_tuple(self, is_shared):
        return self._read_sequence(is_shared, self._stream.read_length(), tuple)

    def _read_tuple0(self, is_shared):
        return self._read_sequence(is_shared, 0, tuple)

    def _read_tuple1(self, is_shared):
        return self._read_sequence(is_shared, 1, tuple)

    def _read_tuple2(self, is_shared):
        return self._read_sequence(is_shared, 2, tuple)

    def _read_list(self, is_shared):
        return self._read_sequence(is_shared, self._stream.read_length(), list)

    def _read_list0(self, is_shared):
        return self._read_sequence(is_shared, 0, list)

    def _read_list1(self, is_shared):
        return self._read_sequence(is_shared, 1, list)

    def _read_sequence(self, is_shared, length, container):
        # Sequence is registered before its contents are read, as those may refer back to it
        items = []
        index = self._stream.mark_shared(items) if is_shared else None
        for _ in range(length):
            items.append(self._route_object())
        if container is tuple:
            items = tuple(items)
            if index is not None:
                self._stream.update_shared(index, items)
        return items

    def _read_dict(self, is_shared):
        length = self._stream.read_length()
        container = {}
        if is_shared:
            self._stream.mark_shared(container)
        for _ in range(length):
            # Value comes before the key it belongs to
            value = self._route_object()
            key = self._route_object()
            container[key] = value
        return container

    ################################################################################################
    # Objects
    ################################################################################################
    def _read_global(self, is_shared):
        obj = GlobalReference(self._stream.read(self._stream.read_length()))
        if is_shared:
            self._stream.mark_shared(obj)
        return obj

    def _read_instance(self, is_shared):
        index = self._stream.mark_shared(None) if is_shared else None
        guid = self._guid_of(self._route_object())
        state = self._route_object()
        obj = MarshalObject(guid, state=state)
        if index is not None:
            self._stream.update_shared(index, obj)
        return obj

    def _read_reduce(self, is_shared):
        index = self._stream.mark_shared(None) if is_shared else None
        contents = self._route_object()
        state = contents[2] if len(contents) > 2 else None
        obj = MarshalObject(self._guid_of(contents[0]), state=state, args=contents[1])
        if index is not None:
            self._stream.update_shared(index, obj)
        self._read_iterators(obj)
        return obj

    def _read_newobj(self, is_shared):
        index = self._stream.mark_shared(None) if is_shared else None
        contents = self._route_object()
        args = contents[0]
        state = contents[1] if len(contents) > 1 else None
        obj = MarshalObject(self._guid_of(args[0]), state=state, args=tuple(args[1:]))
        if index is not None:
            self._stream.update_shared(index, obj)
        self._read_iterators(obj)
        return obj

    def _read_iterators(self, obj):
        items = []
        while not self._read_marker():
            items.append(self._route_object())
        obj.list_items = items
        entries = {}
        while not self._read_marker():
            key = self._route_object()
            entries[key] = self._route_object()
        obj.dict_items = entries

    def _read_marker(self):
        # Markers are never shared, thus the tag is compared as-is
        if self._stream.peek_tag() != Type.MARK:
            return False
        self._stream.read(1)
        return True

    def _guid_of(self, reference):
        if isinstance(reference, GlobalReference):
            reference = reference.name
        if isinstance(reference, bytes):
            try:
                return reference.decode('cp1252')
            except UnicodeDecodeError as e:
                raise MarshalError('unusable guid at offset {}: {}'.format(self._stream.pos, e))
        return reference

    def _read_dbrow(self, is_shared):
        descriptor = RowDescriptor.build_from_marshalled(self._route_object())
        row = descriptor.unpack(self._stream.read(self._stream.read_length()))
        # Values of object columns are not packed, they follow the row one by one
        for name in descriptor.object_names:
            row[name] = self._route_object()
        if is_shared:
            self._stream.mark_shared(row)
        return row

    def _read_wstream(self, is_shared):
        """Marshal stream embedded into another one, as a length-prefixed blob."""
        return Unmarshaller(self._stream.read(self._stream.read_length())).load()

    def _read_reference(self, is_shared):
        return self._stream.get_shared(self._stream.read_length())

    def _read_crc_check(self, is_shared):
        declared = self._stream.unpack(U32)
        # Checksum covers all the data past itself
        actual = zlib.adler32(self._stream.data[self._stream.pos:])
        if actual != declared:
            raise MarshalError('bad checksum: stream declares {}, data checksums to {}'.format(declared, actual))
        return self._route_object()

    def _read_mark(self, is_shared):
        raise MarshalError('marker token at offset {} is not expected here'.format(self._stream.pos - 1))

    _readers = {
        Type.NONE: _read_none,
        Type.TRUE: _read_true,
        Type.FALSE: _read_false,
        Type.INT64: _read_int64,
        Type.INT32: _read_int32,
        Type.INT16: _read_int16,
        Type.INT8: _read_int8,
        Type.INT_N1: _read_int_n1,
        Type.INT_0: _read_int_0,
        Type.INT_1: _read_int_1,
        Type.FLOAT: _read_float,
        Type.FLOAT_0: _read_float_0,
        Type.LONG: _read_long,
        Type.STR: _read_str,
        Type.STR_EMPTY: _read_str_empty,
        Type.STR_CHAR: _read_str_char,
        Type.STR_SHORT: _read_str_short,
        Type.STR_TABLE: _read_str_table,
        Type.UNICODE: _read_unicode,
        Type.UNICODE_0: _read_unicode_0,
        Type.UNICODE_1: _read_unicode_1,
        Type.UTF8_OBSOLETE: _read_utf8,
        Type.BUFFER: _read_buffer,
        Type.TUPLE: _read_tuple,
        Type.TUPLE0: _read_tuple0,
        Type.TUPLE1: _read_tuple1,
        Type.TUPLE2: _read_tuple2,
        Type.LIST: _read_list,
        Type.LIST0: _read_list0,
        Type.LIST1: _read_list1,
        Type.DICT: _read_dict,
        Type.GLOBAL: _read_global,
        Type.INSTANCE: _read_instance,
        Type.DBROW: _read_dbrow,
        Type.REDUCE: _read_reduce,
        Type.NEWOBJ: _read_newobj,
        Type.WSTREAM: _read_wstream,
        Type.REFERENCE: _read_reference,
        Type.CRC_CHECK: _read_crc_check,
        Type.MARK: _read_mark}


class Stream:
    """Cursor over marshal data"""

    def __init__(self, data):
        self.data = data
        self.pos = 0
        self.end = len(data)
        self.shared = []
        self.mapping = []
        self.shared_used = 0

    def read(self, size):
        end = self.pos + size
        if size < 0 or end > self.end:
            raise MarshalError('read of {} bytes at offset {} runs past end of stream ({})'.format(size, self.pos, self.end))
        chunk = self.data[self.pos:end]
        self.pos = end
        return chunk

    def unpack(self, unpacker):
        return unpacker.unpack(self.read(unpacker.size))[0]

    def read_length(self):
        """Lengths are one byte, with 0xff meaning 32-bit sized object."""
        value = ord(self.read(1))
        if value == 0xff:
            return self.unpack(I32)
        return value

    def peek_tag(self):
        if self.pos >= self.end:
            raise MarshalError('expected a type tag at offset {}, but stream ended'.format(self.pos))
        return self.data[self.pos]

    def mark_shared(self, obj):
        if self.shared_used >= len(self.mapping):
            raise MarshalError('shared object table overflow at offset {}'.format(self.pos))
        index = self.mapping[self.shared_used] - 1
        self.shared_used += 1
        if not 0 <= index < len(self.shared):
            raise MarshalError('bogus shared object index {}'.format(index + 1))
        self.shared[index] = obj
        return index

    def update_shared(self, index, obj):
        self.shared[index] = obj

    def get_shared(self, number):
        if not 1 <= number <= len(self.shared):
            raise MarshalError('reference to shared object {} is out of range'.format(number))
        obj = self.shared[number - 1]
        if obj is None:
            raise MarshalError('reference to shared object {} which is not read yet'.format(number))
        return obj


class GlobalReference:
    """Stand-in for a client class referred to by name."""

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return 'GlobalReference({!r})'.format(self.name)


class MarshalObject:

    def __init__(self, guid, state=None, args=None, list_items=None, dict_items=None):
        self.__guid__ = guid
        self.state = state
        self.args = args
        self.list_items = list_items if dict_items is not None else ()
        self.dict_items = dict_items if dict_items is not None else {}

    def __repr__(self):
        return 'MarshalObject({!r})'.format(self.__guid__)
