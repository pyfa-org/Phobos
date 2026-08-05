import os
import pickle
import shutil
import struct
import tempfile
import unittest

from miner.fsd_binary import FsdSchemaError, load_fsd_file


U32 = struct.Struct('<I')


class FsdBinaryReaderTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix='phobos-fsd-test-')

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def _path(self, name):
        return os.path.join(self.temp_dir, name)

    def _write_embedded(self, name, schema, payload):
        path = self._path(name)
        raw_schema = pickle.dumps(schema, protocol=0)
        with open(path, 'wb') as output:
            output.write(U32.pack(len(raw_schema)))
            output.write(raw_schema)
            output.write(payload)
        return path

    @staticmethod
    def _dict_schema(indexed):
        footer_attributes = {
            'key': {'type': 'int', 'min': 0, 'size': 4},
            'offset': {'type': 'int', 'min': 0, 'size': 4}}
        footer_item_size = 8
        if indexed:
            footer_attributes['size'] = {
                'type': 'int', 'min': 0, 'size': 4}
            footer_item_size = 12
        schema = {
            'type': 'dict',
            'keyTypes': {'type': 'int', 'min': 0, 'size': 4},
            'valueTypes': {'type': 'int', 'min': 0, 'size': 4},
            'keyFooter': {
                'type': 'list',
                'fixedItemSize': footer_item_size,
                'itemTypes': {
                    'type': 'object',
                    'size': footer_item_size,
                    'attributes': footer_attributes}}}
        if indexed:
            schema['buildIndex'] = True
        return schema

    @staticmethod
    def _dict_payload(indexed):
        values = struct.pack('<II', 10, 20)
        if indexed:
            footer = U32.pack(2) + struct.pack(
                '<iiiiii', 1, 0, 4, 2, 4, 4)
        else:
            footer = U32.pack(2) + struct.pack('<iiii', 1, 0, 2, 4)
        object_size = len(values) + len(footer) + U32.size
        return U32.pack(object_size) + values + footer + U32.pack(len(footer))

    def test_embedded_fixed_size_list(self):
        schema = {
            'type': 'list',
            'fixedItemSize': 4,
            'itemTypes': {'type': 'int', 'min': 0, 'size': 4}}
        payload = struct.pack('<IIII', 3, 7, 11, 13)
        path = self._write_embedded('numbers.static', schema, payload)
        self.assertEqual(load_fsd_file(path), (7, 11, 13))

    def test_nonindexed_dictionary_footer(self):
        path = self._write_embedded(
            'dictionary.static', self._dict_schema(False),
            self._dict_payload(False))
        self.assertEqual(load_fsd_file(path), {1: 10, 2: 20})

    def test_indexed_dictionary_footer(self):
        path = self._write_embedded(
            'index.static', self._dict_schema(True),
            self._dict_payload(True))
        self.assertEqual(load_fsd_file(path), {1: 10, 2: 20})

    def test_external_optimized_yaml_schema(self):
        data_path = self._path('external.static')
        schema_path = self._path('external.schema')
        with open(data_path, 'wb') as output:
            output.write(struct.pack('<III', 2, 101, 202))
        with open(schema_path, 'wb') as output:
            output.write(
                b'type: list\n'
                b'fixedItemSize: 4\n'
                b'itemTypes: {type: int, min: 0, size: 4}\n')
        self.assertEqual(
            load_fsd_file(data_path, schema_path=schema_path), (101, 202))

    def test_embedded_schema_rejects_arbitrary_globals(self):
        raw_schema = pickle.dumps(os.system, protocol=0)
        path = self._path('unsafe.static')
        with open(path, 'wb') as output:
            output.write(U32.pack(len(raw_schema)))
            output.write(raw_schema)
        with self.assertRaises(FsdSchemaError):
            load_fsd_file(path)


if __name__ == '__main__':
    unittest.main()
