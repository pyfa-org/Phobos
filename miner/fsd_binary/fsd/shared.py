from os import SEEK_END
from struct import Struct

from .exception import FsdFormatError

# Unsigned ints
U8 = Struct('<B')
U16 = Struct('<H')
U32 = Struct('<I')
U64 = Struct('<Q')
# Signed ints
I32 = Struct('<i')
# Floats
F32 = Struct('<f')
F64 = Struct('<d')
# Composite types
V2F32 = Struct('<ff')
V2F64 = Struct('<dd')
V3F32 = Struct('<fff')
V3F64 = Struct('<ddd')
V4F32 = Struct('<ffff')
V4F64 = Struct('<dddd')
# Auxiliary
KEY_OFFSET = Struct('<ii')
KEY_OFFSET_SIZE = Struct('<iii')


def get_stream_size(stream):
    current = stream.tell()
    stream.seek(0, SEEK_END)
    size = stream.tell()
    stream.seek(current)
    return size


def read_exact_at(stream, offset, size, path):
    if offset < 0 or size < 0:
        raise FsdFormatError('invalid file read at {} offset {} for {} bytes'.format(path, offset, size))
    stream.seek(offset)
    data = stream.read(size)
    if len(data) != size:
        raise FsdFormatError('short file read at {} offset {}: expected {}, received {}'.format(path, offset, size, len(data)))
    return data


def read_u32_at(stream, offset, path):
    return U32.unpack(read_exact_at(stream, offset, U32.size, path))[0]
