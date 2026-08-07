from .base import MachoNetBase
from .unmarshal import MarshalError


class MachoNetCallsMiner(MachoNetBase):
    """Class, responsible for fetching data from EVE client's remote service call cache."""

    name = 'mn_cached_calls'
    _cache_dir = 'CachedMethodCalls'

    def _get_container_name(self, entity_name):
        call_info = entity_name
        # Info has one of 2 following formats:
        # - ((service name, service arg1, service arg2, ...), call name, call arg1, call arg2, ...)
        # - (service name, call name, call arg1, call arg2, ...)
        # Here we parse info structure according to one of these formats
        svc_info = call_info[0]
        call_info = call_info[1:]
        if isinstance(svc_info, (tuple, list)):
            svc_name = svc_info[0]
            svc_args = svc_info[1:]
        else:
            svc_name = svc_info
            svc_args = ()
        call_name = call_info[0]
        call_args = call_info[1:]
        svc_args_line = u', '.join(unicode(a) for a in svc_args)
        call_args_line = u', '.join(unicode(a) for a in call_args)
        return u'{}({})_{}({})'.format(svc_name, svc_args_line, call_name, call_args_line)

    def _get_payload(self, cached_entity):
        """Cached call carries plenty of call metadata, we are after the returned value only."""
        try:
            return cached_entity['lret']
        except (TypeError, KeyError):
            raise MarshalError('cached call result does not carry a return value')
