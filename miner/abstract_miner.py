from abc import ABCMeta, abstractmethod


class AbstractMiner(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def tablename_iter(self):
        pass

    @abstractmethod
    def get_table(self, table_name):
        pass
