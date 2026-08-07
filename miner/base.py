from abc import ABC, abstractmethod


class BaseMiner(ABC):
    """
    Abstract class, which defines interface to all data miners
    used in Phobos.
    """

    @abstractmethod
    def contname_iter(self):
        """Provide an iterator over containers provided by miner."""
        raise NotImplementedError

    @abstractmethod
    def get_data(self, container_name, **kwargs):
        """Fetch data from specified container."""
        raise NotImplementedError

    @property
    def name(self):
        """Return miner group name, which can be used as output affix."""
        return self.raw_name

    @property
    def raw_name(self):
        """Return miner class name."""
        return type(self).__name__

    def _container_not_found(self, cont_name):
        msg = 'container "{}" is not available for miner {}'.format(cont_name, type(self).__name__)
        raise ContainerNameError(msg)


class ContainerNameError(Exception):
    """
    When container with requested name is not available,
    this exception is raised by miners.
    """
