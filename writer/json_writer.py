import json
import os.path

from .abstract_writer import AbstractWriter


class JsonWriter(AbstractWriter):
    def __init__(self, folder, indent=None):
        self.folder = folder
        self.indent = indent

    def write(self, table_name, lines):
        if not os.path.exists(self.folder):
            os.makedirs(self.folder, mode=0o755)
        json.dump(
            lines,
            open(os.path.join(self.folder, '{}.json'.format(table_name)), 'w'),
            indent=self.indent,
            encoding='cp1252'
        )
