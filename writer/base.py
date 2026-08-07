from abc import ABC, abstractmethod


class BaseWriter(ABC):
    """
    Abstract class, which defines interface to classes
    which write data into some kind of persistent storage.
    """

    @abstractmethod
    def write(self, miner_name, container_name, container_data):
        raise NotImplementedError
