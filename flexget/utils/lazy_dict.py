from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin


import logging
from collections import MutableMapping

log = logging.getLogger('lazy_lookup')


class LazyLookup(object):
    """
    This class stores the information to do a lazy lookup for a LazyDict. An instance is stored as a placeholder value
    for any key that can be lazily looked up. There should be one instance of this class per LazyDict.
    """

    def __init__(self, store):
        self.store = store
        # These two lists should always match up
        self.func_list = []
        self.key_list = []

    def add_func(self, func, keys):
        if func not in self.func_list:
            self.func_list.append(func)
            self.key_list.append(keys)

    def __getitem__(self, key):
        from flexget.plugin import PluginError
        while self.store.is_lazy(key):
            index = next((i for i, keys in enumerate(self.key_list) if key in keys), None)
            if index is None:
                # All lazy lookup functions for this key were tried unsuccessfully
                return None
            func = self.func_list.pop(index)
            self.key_list.pop(index)
            try:
                func(self.store)
            except PluginError as e:
                e.log.info(e)
            except Exception as e:
                log.error('Unhandled error in lazy lookup plugin')
                from flexget.manager import manager
                if manager:
                    manager.crash_report()
                else:
                    log.debug('Traceback', exc_info=True)
        return self.store[key]

    def __repr__(self):
        return '<LazyLookup(%r)>' % self.func_list


class LazyDict(MutableMapping):
    def __init__(self, *args, **kwargs):
        self.store = dict(*args, **kwargs)

    def __setitem__(self, key, value):
        self.store[key] = value

    def __len__(self):
        return len(self.store)

    def __iter__(self):
        return iter(self.store)

    def __delitem__(self, key):
        del self.store[key]

    def __getitem__(self, key):
        item = self.store[key]
        if isinstance(item, LazyLookup):
            return item[key]
        return item

    def __copy__(self):
        return type(self)(self.store)

    copy = __copy__

    def get(self, key, default=None, eval_lazy=True):
        """
        Adds the `eval_lazy` keyword argument to the normal :func:`dict.get` method.

        :param bool eval_lazy: If False, the default will be returned rather than evaluating a lazy field.
        """
        item = self.store.get(key, default)
        if isinstance(item, LazyLookup):
            if eval_lazy:
                try:
                    return item[key]
                except KeyError:
                    return default
            else:
                return default
        return item

    @property
    def _lazy_lookup(self):
        """
        The LazyLookup instance for this LazyDict.
        If one is already stored in this LazyDict, it is returned, otherwise a new one is instantiated.
        """
        for val in self.store.values():
            if isinstance(val, LazyLookup):
                return val
        return LazyLookup(self)

    def register_lazy_func(self, func, keys):
        """Register a list of fields to be lazily loaded by callback func.

        :param list keys:
          List of key names that `func` can provide.
        :param func:
          Callback function which is called when lazy key needs to be evaluated.
          Function call will get this LazyDict instance as a parameter.
          See :class:`LazyLookup` class for more details.
        """
        ll = self._lazy_lookup
        ll.add_func(func, keys)
        for key in keys:
            if key not in self.store:
                self[key] = ll

    def is_lazy(self, key):
        """
        :param key: Key to check
        :return: True if value for key is lazy loading.
        :rtype: bool
        """
        return isinstance(self.store.get(key), LazyLookup)
