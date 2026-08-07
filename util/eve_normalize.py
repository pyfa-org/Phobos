import inspect
import types
from collections import OrderedDict


class EveNormalizer(object):
    """
    Class, which 'flattens' indexed structures into list of
    'rows' and converts all eve-specific data structures into
    python built-in types.
    """

    def __init__(self):
        self._loader_module = None

    def run(self, eve_container, loader_module=None):
        """
        Entry point for conversion jobs. Runs method which recursively
        changes contents of passed container to present them in pythonized
        data structures.
        """
        self._loader_module = loader_module
        data = self._route_object(eve_container)
        return data

    def _route_object(self, obj):
        """
        Pick proper method for passed object and invoke it.
        """
        # Primitive objects do not need any conversion
        if type(obj) in self._primitives:
            return obj
        # Try strict class/guid matching first
        cls = type(obj)
        try:
            method = self._class_match[cls]
        except KeyError:
            pass
        else:
            return method(self, obj)
        # __guid__ is available for many objects exposed by the client,
        # use class name as fallback only when it's not available
        cls_name = getattr(obj, '__guid__', type(obj).__name__)
        try:
            method = self._name_match[cls_name]
        except KeyError:
            pass
        else:
            return method(self, obj)
        # Try to find parent class for passed object, and if we
        # have any in our records - run handler for it
        for candidate_cls in self._subclass_match:
            if isinstance(obj, candidate_cls):
                method = self._subclass_match[candidate_cls]
                return method(self, obj)
        # Stuff specific to FSD binary format
        if self._loader_module is not None:
            # Check if class is defined in passed loader, if it is, then
            # we're dealing with FSD binary item for certain
            if inspect.getmodule(type(obj)) is self._loader_module:
                return self.pythonize_fsdbuilt_item(obj)
            # FSD contains a bunch of vector classes which are defined outside of
            # loader (shown as defined in builtins), process them separately
            if type(obj).__name__.endswith('_vector'):
                return self.pythonize_fsdbuilt_item(obj, ignore_attrs=(
                    'n_fields', 'n_sequence_fields', 'n_unnamed_fields'))
        # If we got here, routing failed
        msg = 'unable to route {}'.format(type(obj))
        guid = getattr(obj, '__guid__', None)
        if guid is not None:
            msg = '{} (guid {})'.format(msg, guid)
        raise UnknownContainerTypeError(msg)

    def _pythonize_iterable(self, obj):
        """
        For objects which have access interface similar to python
        iterables - convert contents and return them as tuple.
        """
        return tuple(self._route_object(i) for i in obj)

    def _pythonize_map(self, obj):
        """
        For objects which have access interface similar to python
        dictionaries - convert keys and values and return as dict.
        """
        container = {}
        for key, value in obj.iteritems():
            proc_key = self._route_object(key)
            proc_value = self._route_object(value)
            container[proc_key] = proc_value
        return container

    def _pythonize_string(self, obj):
        """
        Sometimes EVE has non-ASCII symbols in non-unicode strings,
        default encoding for these is cp1252, here we ensure they are
        converted to unicode so we don't have to run any additional
        processing on them elsewhere.
        """
        return obj.decode('cp1252')

    def _pythonize_fsd_named_vector(self, obj):
        """
        Named vectors resemble tuples/lists, but contain name data for
        their fields, thus we convert them into dicts.
        """
        container = {}
        name_data = obj.schema['aliases']
        for name, index in name_data.iteritems():
            value = obj.data[index]
            proc_name = self._route_object(name)
            proc_value = self._route_object(value)
            container[proc_name] = proc_value
        return container

    def _pythonize_fsd_object(self, obj):
        """
        FSD_Object is similar to regular python objects - but unlike them,
        list of accessible attributes is stored in 'attributes' attribute.
        """
        container = {}
        for key in obj.attributes:
            # Sometimes values are missing
            value = getattr(obj, key, None)
            proc_key = self._route_object(key)
            proc_value = self._route_object(value)
            container[proc_key] = proc_value
        return container

    def _pythonize_pyobj(self, obj):
        """
        KeyVal is a python-like object, where attributes/values are stored
        as object attributes.
        """
        return self._pythonize_map(obj.__dict__)

    def _pythonize_marshal_set(self, obj):
        """
        Set data is stored in marshal obj's argument.
        """
        return self._pythonize_iterable(obj.args[0])

    def _pythonize_marshal_keyval(self, obj):
        """
        Types with KeyVal guid store their useful info on marshal obj's state, so handle only it.
        """
        return self._pythonize_map(obj.state)

    def _pythonize_marshal_rowset(self, obj):
        """
        Regular rowset stores all the necessary data in marshal obj's state, separately header, 
        separately rows themselves. Here they are merged to expose just rows.
        """
        header = obj.state['header']
        return tuple(self._pythonize_map(dict(zip(header, line))) for line in obj.state['lines'])

    def _pythonize_marshal_carbon_rowset(self, obj):
        """
        Just a set of rows stored on marshal obj, expose them like regular iterable without extra 
        processing.
        """
        return self._pythonize_iterable(obj.list_items)

    def _pythonize_marshal_carbon_indexed_rowset(self, obj):
        """
        Similar to regular carbon rowset, but with an index.

        Old implementation exposed it as a regular rowset, while most of Phobos containers expose
        data as-is. So, in new implementation I decided to switch to exposing rows with an index,
        instead of just rows.
        """
        return self._pythonize_map(obj.dict_items)

    def pythonize_fsdbuilt_item(self, obj, ignore_attrs=()):
        item = {}
        for attr_name in dir(obj):
            if attr_name.startswith('__') and attr_name.endswith('__'):
                continue
            if attr_name in ignore_attrs:
                continue
            item[attr_name] = self._route_object(getattr(obj, attr_name))
        return item

    _primitives = (
        types.NoneType,
        types.BooleanType,
        types.FloatType,
        types.IntType,
        types.LongType,
        types.UnicodeType)

    _class_match = {
        types.StringType: _pythonize_string,
        types.ListType: _pythonize_iterable,
        types.TupleType: _pythonize_iterable}

    _name_match = {
        # FSD-related classes
        'FSD_Dict': _pythonize_map,
        'FSD_MultiIndex': _pythonize_map,
        'FSD_NamedVector': _pythonize_fsd_named_vector,
        'FSD_Object': _pythonize_fsd_object,
        '_FixedSizeList': _pythonize_iterable,
        '_VariableSizedList': _pythonize_iterable,
        # FSD binary specific classes
        'dict': _pythonize_map,  # cfsd.dict
        'list': _pythonize_iterable,  # cfsd.list
        # Classes extracted via unmarshalling cached data
        '__builtin__.set': _pythonize_marshal_set,
        'utillib.KeyVal': _pythonize_marshal_keyval,
        'eve.common.script.sys.rowset.Rowset': _pythonize_marshal_rowset,
        'carbon.common.script.sys.crowset.CRowset': _pythonize_marshal_carbon_rowset,
        'carbon.common.script.sys.crowset.CIndexedRowset': _pythonize_marshal_carbon_indexed_rowset,
        # Misc
        'universe.SolarSystemWrapper': _pythonize_pyobj}

    _subclass_match = OrderedDict([
        # Includes dictionaries and FSDLiteStorage
        (types.DictType, _pythonize_map)])


class UnknownContainerTypeError(Exception):
    """
    Raised when normalizer doesn't know what to do
    with passed object.
    """
