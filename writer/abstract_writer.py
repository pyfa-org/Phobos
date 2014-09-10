from abc import ABCMeta, abstractmethod


class AbstractWriter(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def write(self, table_name, lines):
        pass
