from struct import Struct

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
