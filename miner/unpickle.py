import pickle

from miner.base import BaseMiner
from util import cachedproperty


class PickleMiner(BaseMiner):
    """
    Class, which attempts to get data from resource pickles.

    This can fail due to data relying on libraries not present in Phobos.
    """

    name = 'resource_pickle'

    def __init__(self, resbrowser):
        self._resbrowser = resbrowser

    def contname_iter(self):
        for container_name in sorted(self._contname_respath_map):
            yield container_name

    def get_data(self, container_name, **kwargs):
        try:
            resource_path = self._contname_respath_map[container_name]
        except KeyError:
            self._container_not_found(container_name)
        else:
            resource_data = self._resbrowser.get_file_data(resource_path)
            data = pickle.loads(resource_data)
            return data

    @cachedproperty
    def _contname_respath_map(self):
        """
        Map between container names and resource path names to pickle files.
        Format: {container name: resource path to pickle}
        """
        pickle_ext = '.pickle'
        contname_respath_map = {}
        for resource_path in self._resbrowser.respath_iter():
            if not resource_path.endswith(pickle_ext):
                continue
            container_name = resource_path[:-len(pickle_ext)]
            contname_respath_map[container_name] = resource_path
        return contname_respath_map
