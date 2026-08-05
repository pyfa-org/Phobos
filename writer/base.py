from abc import ABCMeta, abstractmethod


class BaseWriter(object):
    """
    Abstract class, which defines interface to classes
    which write data into some kind of persistent storage.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def write(self, miner_name, container_name, container_data):
        raise NotImplementedError
