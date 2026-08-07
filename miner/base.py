from abc import ABCMeta, abstractmethod


class BaseMiner(object):
    """Abstract class, which defines interface to all data miners used in Phobos."""
    __metaclass__ = ABCMeta

    @abstractmethod
    def contname_iter(self):
        """Iterator over containers discovered by miner."""
        raise NotImplementedError

    @abstractmethod
    def get_data(self, container_name, **kwargs):
        """Fetch data from specified container."""
        raise NotImplementedError

    def discovery_error_iter(self):
        """No errors as default implementation."""
        return iter(())

    @property
    def name(self):
        """Return miner group name, which can be used as output affix."""
        return self.raw_name

    @property
    def raw_name(self):
        """Return miner class name."""
        return type(self).__name__

    def _container_not_found(self, cont_name):
        msg = u'container "{}" is not available for miner {}'.format(cont_name, type(self).__name__)
        raise ContainerNotFoundError(msg)


class DiscoveredData(object):
    """Convenience container for miners which can have errors during discovery."""

    def __init__(self, data):
        self.data = data
        self.errors = []


class DiscoveryError(Exception):
    """Errors recorded during discovery are represented by this class."""


class ContainerNotFoundError(Exception):
    """When container with requested name is not available, this exception is raised by miners."""
