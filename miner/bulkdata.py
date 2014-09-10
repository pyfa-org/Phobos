from reverence import blue

from .abstract_miner import AbstractMiner


class BulkdataMiner(AbstractMiner):

    def __init__(self, path_eve, path_cache, server):
        eve = blue.EVE(path_eve, cachepath=path_cache, server=server)
        self.cfg = eve.getconfigmgr()

    def tablename_iter(self):
        for table_name in self.cfg.tables:
            yield table_name

    def get_table(self, table_name):
        lines = []
        return lines
