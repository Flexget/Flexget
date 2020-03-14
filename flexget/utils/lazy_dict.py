from collections.abc import MutableMapping
from typing import Any, Callable, Iterable, List, Mapping, NamedTuple, Sequence

from loguru import logger

logger = logger.bind(name='lazy_lookup')


class LazyCallee(NamedTuple):
    func: Callable
    keys: Sequence
    args: Sequence
    kwargs: Mapping


class LazyLookup:
    """
    This class stores the information to do a lazy lookup for a LazyDict. An instance is stored as a placeholder value
    for any key that can be lazily looked up. There should be one instance of this class per LazyDict.
    """

    def __init__(self, store: 'LazyDict') -> None:
        self.store = store
        self.callee_list: List[LazyCallee] = []

    def add_func(self, func: Callable, keys: Sequence, args: Sequence, kwargs: Mapping) -> None:
        self.callee_list.append(LazyCallee(func, keys, args, kwargs))

    def __getitem__(self, key) -> Any:
        from flexget.plugin import PluginError

        while self.store.is_lazy(key):
            index = next(
                (i for i, callee in enumerate(self.callee_list) if key in callee.keys), None
            )
            if index is None:
                # All lazy lookup functions for this key were tried unsuccessfully
                return None
            callee = self.callee_list.pop(index)
            try:
                callee.func(self.store, *(callee.args or []), **(callee.kwargs or {}))
            except PluginError as e:
                e.logger.info(e)
            except Exception as e:
                logger.error('Unhandled error in lazy lookup plugin: {}', e)
                from flexget.manager import manager

                if manager:
                    manager.crash_report()
                else:
                    logger.opt(exception=True).debug('Traceback')
        return self.store[key]

    def __repr__(self):
        return '<LazyLookup(%r)>' % self.callee_list


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

    def get(
        self, key, default: Any = None, eval_lazy: bool = True
    ) -> Any:  # pylint: disable=W0221
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
    def _lazy_lookup(self) -> LazyLookup:
        """
        The LazyLookup instance for this LazyDict.
        If one is already stored in this LazyDict, it is returned, otherwise a new one is instantiated.
        """
        for val in self.store.values():
            if isinstance(val, LazyLookup):
                return val
        return LazyLookup(self)

    def register_lazy_func(
        self, func: Callable[[Mapping], None], keys: Iterable, args: Sequence, kwargs: Mapping
    ):
        """Register a list of fields to be lazily loaded by callback func.

        :param func:
          Callback function which is called when lazy key needs to be evaluated.
          Function call will get this LazyDict instance as a parameter.
          See :class:`LazyLookup` class for more details.
        :param keys:
          List of key names that `func` can provide.
        :param args: Arguments which will be passed to `func` when called.
        :param kwargs: Keyword arguments which will be passed to `func` when called.
        """
        ll = self._lazy_lookup
        ll.add_func(func, keys, args, kwargs)
        for key in keys:
            if key not in self.store:
                self[key] = ll

    def is_lazy(self, key) -> bool:
        """
        :param key: Key to check
        :return: True if value for key is lazy loading.
        :rtype: bool
        """
        return isinstance(self.store.get(key), LazyLookup)
