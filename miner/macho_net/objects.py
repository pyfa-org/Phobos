import zlib

from .base import MachoNetBase
from .unmarshal import MarshalError, Unmarshaller


class MachoNetObjectsMiner(MachoNetBase):
    """Class, responsible for fetching data from EVE client's cached object store."""

    name = 'mn_cached_objects'
    _cache_dir = 'CachedObjects'

    def _get_container_name(self, entity_name):
        # Name can be pretty much anything, so format it about as it is
        if isinstance(entity_name, (tuple, list)):
            return u', '.join(self.__format_name_part(p) for p in entity_name)
        return self.__format_name_part(entity_name)

    def __format_name_part(self, part):
        if isinstance(part, (tuple, list)):
            return u'({})'.format(u', '.join(self.__format_name_part(p) for p in part))
        return unicode(part)

    def _get_payload(self, cached_entity):
        try:
            payload = cached_entity.state[4]
            is_compressed = cached_entity.state[5]
        except (AttributeError, IndexError, TypeError):
            raise MarshalError('cached object has data in unexpected format')
        if not is_compressed:
            return payload
        try:
            payload = zlib.decompress(payload)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            raise MarshalError('unable to decompress cached object: {}'.format(e))
        return Unmarshaller(payload).load()
