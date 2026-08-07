"""
Format is reimplemented after PyRowSet.cpp from the blue library
(https://github.com/carbonengine/blue).
"""

import struct

from .exception import MarshalError


class DbType:
    """Column types, as defined in the blue's rowset source."""
    EMPTY = 0
    I2 = 2
    I4 = 3
    R4 = 4
    R8 = 5
    CY = 6
    BOOL = 11
    I1 = 16
    UI1 = 17
    UI2 = 18
    UI4 = 19
    I8 = 20
    UI8 = 21
    FILETIME = 64
    BYTES = 128
    STR = 129
    WSTR = 130
    DBTIMESTAMP = 135


class RowDescriptor:
    """Tells where each column of a packed row sits within its data."""

    @classmethod
    def build_from_marshalled(cls, marshalled_descriptor):
        try:
            return cls(tuple(marshalled_descriptor.args[0]))
        except (AttributeError, IndexError, TypeError):
            raise MarshalError('database row is not preceded by a usable row descriptor')


    def __init__(self, columns):
        self._columns = tuple(columns)
        # Format: [(column name, column type, offset, size), ...]
        self._layout = []
        self._object_names = []
        self._data_length = 0
        self._null_offset = 0
        self._measure()

    @property
    def object_names(self):
        """Names of the columns whose values are not part of packed data."""
        return tuple(self._object_names)

    def unpack(self, packed):
        data = self._unpack_rle(packed)
        row = {}
        for null_index, (name, column_type, offset, size) in enumerate(self._layout):
            if self._get_bit(data, self._null_offset + null_index):
                row[name] = None
            elif column_type == DbType.BOOL:
                row[name] = self._get_bit(data, offset)
            else:
                value = self._unpackers[column_type].unpack(data[offset:offset + size])[0]
                # Currency is stored scaled up, to keep it away from floating point until read
                row[name] = value / 10000.0 if column_type == DbType.CY else value
        return row

    def _measure(self):
        """Count columns of every size class, then hand each one its place in the data."""
        sizes = [0] * 6
        real_columns = 0
        classes = []
        for name, column_type in self._columns:
            try:
                size_class = self._size_classes[column_type]
            except KeyError:
                raise MarshalError('unsupported database column type {} in column {!r}'.format(
                    column_type, name))
            classes.append(size_class)
            if column_type in self._object_types:
                self._object_names.append(name)
                real_columns += 1
            elif column_type != DbType.EMPTY:
                real_columns += 1
                sizes[size_class] += 1

        # Largest columns come first, booleans and null flags are packed into bits after them
        offsets = [0] * 6
        offset = 0
        for size_class in (4, 3, 2, 1):
            offsets[size_class] = offset
            offset += sizes[size_class] * (1 << (size_class - 1))
        offset *= 8
        offsets[0] = offset
        offset += sizes[0]
        self._null_offset = offset
        offset += real_columns
        self._data_length = (offset + 7) // 8

        for index, (name, column_type) in enumerate(self._columns):
            if column_type in self._object_types or column_type == DbType.EMPTY:
                continue
            if column_type == DbType.BOOL:
                self._layout.append((name, column_type, offsets[0], -1))
                offsets[0] += 1
            else:
                size = 1 << (classes[index] - 1)
                self._layout.append((name, column_type, offsets[classes[index]], size))
                offsets[classes[index]] += size

    def _unpack_rle(self, data):
        out = []
        written = 0
        run = 0
        nibble = False
        i = 0
        while i < len(data) and written < self._data_length:
            if not nibble:
                run = data[i]
                i += 1
                count = run & 0xf
            else:
                count = (run & 0xf0) >> 4
            nibble = not nibble
            count -= 8
            if count >= 0:
                out.append(b'\x00' * (count + 1))
                written += count + 1
            else:
                while count < 0 and i < len(data):
                    out.append(data[i:i + 1])
                    i += 1
                    written += 1
                    count += 1
        if written < self._data_length:
            out.append(b'\x00' * (self._data_length - written))
        return b''.join(out)

    def _get_bit(self, data, index):
        return bool(data[index // 8] & (1 << (index % 8)))

    _size_classes = {
        DbType.BOOL: 0,
        DbType.I1: 1, DbType.UI1: 1,
        DbType.I2: 2, DbType.UI2: 2,
        DbType.I4: 3, DbType.UI4: 3, DbType.R4: 3,
        DbType.I8: 4, DbType.UI8: 4, DbType.R8: 4, DbType.CY: 4,
        DbType.FILETIME: 4, DbType.DBTIMESTAMP: 4,
        DbType.STR: 5, DbType.WSTR: 5, DbType.BYTES: 5,
        DbType.EMPTY: -1}

    _object_types = (DbType.STR, DbType.WSTR, DbType.BYTES)

    _unpackers = {
        DbType.I1: struct.Struct('<b'), DbType.UI1: struct.Struct('<B'),
        DbType.I2: struct.Struct('<h'), DbType.UI2: struct.Struct('<H'),
        DbType.I4: struct.Struct('<i'), DbType.UI4: struct.Struct('<I'),
        DbType.R4: struct.Struct('<f'), DbType.R8: struct.Struct('<d'),
        DbType.I8: struct.Struct('<q'), DbType.UI8: struct.Struct('<Q'),
        DbType.CY: struct.Struct('<q'), DbType.FILETIME: struct.Struct('<Q'),
        DbType.DBTIMESTAMP: struct.Struct('<Q')}
