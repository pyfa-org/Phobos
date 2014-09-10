import os.path
import sys
from ConfigParser import ConfigParser
from datetime import datetime
from time import mktime

from .abstract_miner import AbstractMiner
from .exception import TableNameError


class MetadataMiner(AbstractMiner):

    def __init__(self, path_eve):
        self.path_eve = path_eve

    def tablename_iter(self):
        for table_name in ('metadata',):
            yield table_name

    def get_table(self, table_name):
        if table_name != 'metadata':
            raise TableNameError('"{}" is not available for this miner'.format(table_name))
        header = ['field_name', 'field_value']
        lines = []
        # Read client version
        try:
            config = ConfigParser()
            config.read(os.path.join(self.path_eve, 'start.ini'))
            eveVersion = config.getint('main', 'build')
        except:
            sys.stderr.write('failed to detect client version\n')
            eveVersion = None
        lines.append({header[0]: 'client_build', header[1]: eveVersion})
        # Generate UNIX-style timestamp of current UTC time
        timestamp = int(mktime(datetime.utcnow().timetuple()))
        lines.append({header[0]: 'dump_time', header[1]: timestamp})
        return lines
