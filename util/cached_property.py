class cachedproperty:
    """
    Decorator class, imitates property behavior, but additionally
    caches results returned by decorated method as attribute of
    instance to which decorated method belongs. As python, when getting
    attribute with certain name, seeks for class instance's attributes
    first, then for methods, it gets cached result. To clear cache, just
    delete cached attribute.
    """

    def __init__(self, method):
        self.__method = method

    def __get__(self, instance, owner):
        # Return descriptor if called from class
        if instance is None:
            return self
        # If called from instance, execute decorated method
        # and store returned value as class attribute, which
        # has the same name as method, then return it to caller
        value = self.__method(instance)
        setattr(instance, self.__method.__name__, value)
        return value
