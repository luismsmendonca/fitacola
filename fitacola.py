from functools import reduce, wraps
from importlib import import_module

try:
    import gevent
    has_gevent=True
except ImportError:
    has_gevent=False


def import_string(dotted_path):
    """Import a dotted module path and return the attribute/class designated by the
    last name in the path. Raise ImportError if the import failed.

    """

    try:
        module_path, class_name = dotted_path.rsplit('.', 1)
    except ValueError:
        msg = "%s doesn't look like a module path" % dotted_path
        raise ImportError(msg)

    module = import_module(module_path)

    try:
        return getattr(module, class_name)
    except AttributeError:
        msg = 'Module "%s" does not define a "%s" attribute/class' % (
            module_path, class_name)
        raise ImportError(msg)


class lazy_object(object):
    """
    Create a proxy or placeholder for another object.
    """

    __slots__ = (
        "obj",
        "_callbacks",
        "_init_callback",
        "_check_and_initialize",
    )

    def __init__(self, init_callback=None):
        self._callbacks = []
        self._init_callback = init_callback
        self.initialize(None)

        def _check_and_initialize(self):
            if self.obj is None:
                if self._init_callback:
                    self.initialize(self._init_callback())
                else:
                    raise AttributeError("Cannot use uninitialized Proxy.")

        self._check_and_initialize = _check_and_initialize

    def initialize(self, obj):
        self.obj = obj
        for callback in self._callbacks:
            callback(obj)

    def attach_callback(self, callback):
        self._callbacks.append(callback)
        return callback

    def passthrough(method):
        def inner(self, *args, **kwargs):
            self._check_and_initialize(self)
            return getattr(self.obj, method)(*args, **kwargs)

        return inner

    # Allow proxy to be used as a context-manager.
    __enter__ = passthrough("__enter__")
    __exit__ = passthrough("__exit__")
    __call__ = passthrough("__call__")

    def __getattr__(self, attr):
        if attr not in self.__slots__:
            self._check_and_initialize(self)
        return getattr(self.obj, attr)

    def __setattr__(self, attr, value):
        if attr not in self.__slots__:
            raise AttributeError("Cannot set attribute on proxy.")

        return super(lazy_object, self).__setattr__(attr, value)

    def __getitem__(self, key):
        self._check_and_initialize(self)
        return self.obj.__getitem__(key)

    def __setitem__(self, key, value):
        self._check_and_initialize(self)
        return self.obj.__setitem__(key, value)


def deep_get(dct, keys, default=None):
    return reduce(lambda d, key: d.get(key, default) if isinstance(d, dict) else default, keys.split("."), dct)

def dict_merge(dct, merge_dct):
    """ Recursive dict merge. Inspired by :meth:``dict.update()``, instead of
    updating only top-level keys, dict_merge recurses down into dicts nested
    to an arbitrary depth, updating keys. The ``merge_dct`` is merged into
    ``dct``.
    :param dct: dict onto which the merge is executed
    :param merge_dct: dct merged into dct
    :return: None
    """
    for k, v in merge_dct.items():
        if (k in dct and isinstance(dct[k], dict)):
            dict_merge(dct[k], merge_dct[k])
        else:
            dct[k] = merge_dct[k]


# ----- gevent/greenlet utils -----
def greenlet():
    def inner_wrapper(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return gevent.spawn(func, *args, **kwargs)
        return wrapper
    return inner_wrapper


def timeout(value):
    def inner_wrapper(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            timeout = gevent.Timeout(value)
            timeout.start()
            resp = func(*args, **kwargs)
            timeout.cancel()
            return resp
        return wrapper
    return inner_wrapper
