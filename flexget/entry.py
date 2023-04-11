import functools
import types
import warnings
from enum import Enum
from typing import Callable, Iterable, Mapping, Optional, Sequence, Union

from loguru import logger

from flexget import plugin
from flexget.utils.lazy_dict import LazyDict, LazyLookup
from flexget.utils.serialization import Serializer, deserialize, serialize
from flexget.utils.template import FlexGetTemplate, render_from_entry

logger = logger.bind(name='entry')


class EntryState(Enum):
    ACCEPTED = 'accepted'
    REJECTED = 'rejected'
    FAILED = 'failed'
    UNDECIDED = 'undecided'

    @property
    def color(self) -> str:
        return {
            EntryState.ACCEPTED: 'green',
            EntryState.REJECTED: 'red',
            EntryState.FAILED: 'RED',
            EntryState.UNDECIDED: 'dim',
        }[self]

    @property
    def log_markup(self) -> str:
        return f'<{self.color}>{self.value.upper()}</>'

    # __str__, __eq__, and __hash__ are make these states almost interchangeable with the old plain string states
    def __str__(self) -> str:
        return self.value

    def __eq__(self, other) -> bool:
        if isinstance(other, str):
            return self.value == other
        return super().__eq__(other)

    def __hash__(self) -> int:
        return hash(self.value)


class EntryUnicodeError(Exception):
    """This exception is thrown when trying to set non-unicode compatible field value to entry."""

    def __init__(self, key: str, value) -> None:
        self.key = key
        self.value = value

    def __str__(self):
        return f'Entry strings must be unicode: {self.key} ({self.value!r})'


class Entry(LazyDict, Serializer):
    """
    Represents one item in task. Must have `url` and *title* fields.

    Stores automatically *original_url* key, which is necessary because
    plugins (eg. urlrewriters) may change *url* into something else
    and otherwise that information would be lost.

    Entry will also transparently convert all ascii strings into unicode
    and raises :class:`EntryUnicodeError` if conversion fails on any value
    being set. Such failures are caught by :class:`~flexget.task.Task`
    and trigger :meth:`~flexget.task.Task.abort`.
    """

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.traces = []
        self._state = EntryState.UNDECIDED
        self._hooks = {'accept': [], 'reject': [], 'fail': [], 'complete': []}
        self.task = None
        self.lazy_lookups = []

        if len(args) == 2:
            kwargs['title'] = args[0]
            kwargs['url'] = args[1]
            args = []

        # Make sure constructor does not escape our __setitem__ enforcement
        self.update(*args, **kwargs)

    def trace(
        self,
        message: Optional[str],
        operation: str = None,
        plugin: str = None,
    ) -> None:
        """
        Adds trace message to the entry which should contain useful information about why
        plugin did not operate on entry. Accept and Reject messages are added to trace automatically.

        :param string message: Message to add into entry trace.
        :param string operation: None, reject, accept or fail
        :param plugin: Uses task.current_plugin by default, pass value to override
        """
        if operation not in (None, 'accept', 'reject', 'fail'):
            raise ValueError('Unknown operation %s' % operation)
        item = (plugin, operation, message)
        if item not in self.traces:
            self.traces.append(item)

    def run_hooks(self, action: str, **kwargs) -> None:
        """
        Run hooks that have been registered for given ``action``.

        :param action: Name of action to run hooks for
        :param kwargs: Keyword arguments that should be passed to the registered functions
        """
        for func in self._hooks[action]:
            func(self, **kwargs)

    def add_hook(self, action: str, func: Callable, **kwargs) -> None:
        """
        Add a hook for ``action`` to this entry.

        :param string action: One of: 'accept', 'reject', 'fail', 'complete'
        :param func: Function to execute when event occurs
        :param kwargs: Keyword arguments that should be passed to ``func``
        :raises: ValueError when given an invalid ``action``
        """
        try:
            self._hooks[action].append(functools.partial(func, **kwargs))
        except KeyError:
            raise ValueError('`%s` is not a valid entry action' % action)

    def on_accept(self, func: Callable, **kwargs) -> None:
        """
        Register a function to be called when this entry is accepted.

        :param func: The function to call
        :param kwargs: Keyword arguments that should be passed to the registered function
        """
        self.add_hook('accept', func, **kwargs)

    def on_reject(self, func: Callable, **kwargs) -> None:
        """
        Register a function to be called when this entry is rejected.

        :param func: The function to call
        :param kwargs: Keyword arguments that should be passed to the registered function
        """
        self.add_hook('reject', func, **kwargs)

    def on_fail(self, func: Callable, **kwargs) -> None:
        """
        Register a function to be called when this entry is failed.

        :param func: The function to call
        :param kwargs: Keyword arguments that should be passed to the registered function
        """
        self.add_hook('fail', func, **kwargs)

    def on_complete(self, func: Callable, **kwargs) -> None:
        """
        Register a function to be called when a :class:`Task` has finished processing this entry.

        :param func: The function to call
        :param kwargs: Keyword arguments that should be passed to the registered function
        """
        self.add_hook('complete', func, **kwargs)

    def accept(self, reason: str = None, **kwargs) -> None:
        if self.rejected:
            logger.debug('tried to accept rejected {!r}', self)
        elif not self.accepted:
            self._state = EntryState.ACCEPTED
            self.trace(reason, operation='accept')
            # Run entry on_accept hooks
            self.run_hooks('accept', reason=reason, **kwargs)

    def reject(self, reason: str = None, **kwargs) -> None:
        # ignore rejections on immortal entries
        if self.get('immortal'):
            reason_str = '(%s)' % reason if reason else ''
            logger.info('Tried to reject immortal {} {}', self['title'], reason_str)
            self.trace(f'Tried to reject immortal {reason_str}')
            return
        if not self.rejected:
            self._state = EntryState.REJECTED
            self.trace(reason, operation='reject')
            # Run entry on_reject hooks
            self.run_hooks('reject', reason=reason, **kwargs)

    def fail(self, reason: Optional[str] = None, **kwargs):
        logger.debug("Marking entry '{}' as failed", self['title'])
        if not self.failed:
            self._state = EntryState.FAILED
            self.trace(reason, operation='fail')
            logger.error('Failed {} ({})', self['title'], reason)
            # Run entry on_fail hooks
            self.run_hooks('fail', reason=reason, **kwargs)

    def complete(self, **kwargs):
        # Run entry on_complete hooks
        self.run_hooks('complete', **kwargs)

    @property
    def state(self) -> EntryState:
        return self._state

    @property
    def accepted(self) -> bool:
        return self._state == EntryState.ACCEPTED

    @property
    def rejected(self) -> bool:
        return self._state == EntryState.REJECTED

    @property
    def failed(self) -> bool:
        return self._state == EntryState.FAILED

    @property
    def undecided(self) -> bool:
        return self._state == EntryState.UNDECIDED

    def __setitem__(self, key, value):
        # Enforce unicode compatibility.
        if isinstance(value, bytes):
            raise EntryUnicodeError(key, value)
        # Coerce any enriched strings (such as those returned by BeautifulSoup) to plain strings to avoid serialization
        # troubles.
        elif (
            isinstance(value, str) and type(value) != str
        ):  # pylint: disable=unidiomatic-typecheck
            value = str(value)

        # url and original_url handling
        if key == 'url':
            if not isinstance(value, (str, LazyLookup)):
                raise plugin.PluginError(
                    'Tried to set {!r} url to {!r}'.format(self.get('title'), value)
                )
            self.setdefault('original_url', value)

        # title handling
        if key == 'title':
            if not isinstance(value, (str, LazyLookup)):
                raise plugin.PluginError('Tried to set title to %r' % value)
            self.setdefault('original_title', value)

        try:
            logger.trace('ENTRY SET: {} = {!r}', key, value)
        except Exception as e:
            logger.debug('trying to debug key `{}` value threw exception: {}', key, e)

        super().__setitem__(key, value)

    def safe_str(self) -> str:
        return f'{self["title"]} | {self["url"]}'

    # TODO: this is too manual, maybe we should somehow check this internally and throw some exception if
    # application is trying to operate on invalid entry
    def isvalid(self) -> bool:
        """
        :return: True if entry is valid. Return False if this cannot be used.
        :rtype: bool
        """
        if 'title' not in self:
            return False
        if 'url' not in self:
            return False
        if not isinstance(self['url'], str):
            return False
        if not isinstance(self['title'], str):
            return False
        return True

    def update_using_map(
        self, field_map: dict, source_item: Union[dict, object], ignore_none: bool = False
    ):
        """
        Populates entry fields from a source object using a dictionary that maps from entry field names to
        attributes (or keys) in the source object.

        :param dict field_map:
          A dictionary mapping entry field names to the attribute in source_item (or keys,
          if source_item is a dict)(nested attributes/dicts are also supported, separated by a dot,)
          or a function that takes source_item as an argument
        :param source_item:
          Source of information to be used by the map
        :param ignore_none:
          Ignore any None values, do not record it to the Entry
        """
        func = dict.get if isinstance(source_item, dict) else getattr
        for field, value in field_map.items():
            if isinstance(value, str):
                v = functools.reduce(func, value.split('.'), source_item)
            else:
                v = value(source_item)
            if ignore_none and v is None:
                continue
            self[field] = v

    def render(self, template: Union[str, FlexGetTemplate], native: bool = False) -> str:
        """
        Renders a template string based on fields in the entry.

        :param template: A template string or FlexGetTemplate that uses jinja2 or python string replacement format.
        :param native: If True, and the rendering result can be all native python types, not just strings.
        :return: The result of the rendering.
        :rtype: string
        :raises RenderError: If there is a problem.
        """
        if not isinstance(template, (str, FlexGetTemplate)):
            raise ValueError(
                'Trying to render non string template or unrecognized template format, got %s'
                % repr(template)
            )
        logger.trace('rendering: {}', template)
        return render_from_entry(template, self, native=native)

    @classmethod
    def serialize(cls, entry: 'Entry') -> dict:
        fields = {}
        for key in entry:
            if key.startswith('_') or entry.is_lazy(key):
                continue
            try:
                fields[key] = serialize(entry[key])
            except TypeError as exc:
                logger.debug('field {} was not serializable. {}', key, exc)
        lazy_lookups = []
        for ll in entry.lazy_lookups:
            try:
                lazy_lookups.append(serialize(ll))
            except TypeError as exc:
                logger.exception(
                    'BUG: Lazy lookup was not compatible with serialization. Please file a bug report: {}',
                    exc,
                )
        return {'fields': fields, 'lazy_lookups': lazy_lookups}

    @classmethod
    def deserialize(cls, data, version) -> 'Entry':
        result = cls()
        for key, value in data['fields'].items():
            result[key] = deserialize(value)
        for lazy_lookup in deserialize(data['lazy_lookups']):
            result.add_lazy_fields(*lazy_lookup)
        return result

    def add_lazy_fields(
        self,
        lazy_func: Union[Callable[['Entry'], None], str],
        fields: Iterable[str],
        args: Sequence = None,
        kwargs: Mapping = None,
    ):
        """
        Add lazy fields to an entry.
        :param lazy_func: should be a funciton previously registered with the `register_lazy_func` decorator,
            or the name it was registered under.
        :param fields: list of fields this function will fill
        :param args: Arguments that will be passed to the lazy lookup function when called.
        :param kwargs: Keyword arguments which will be passed to the lazy lookup function when called.
        """
        if not isinstance(lazy_func, str):
            lazy_func = getattr(lazy_func, 'lazy_func_id', None)
        if lazy_func not in lazy_func_registry:
            raise ValueError(
                'Lazy lookup functions/methods must be registered with the `register_lazy_lookup` decorator'
            )
        # Make sure fields is a plain list. If it is a dict, (or some other iterable) we may try to serialize
        # extra/unserializable stuff.
        fields = list(fields)
        func = lazy_func_registry[lazy_func]
        super().register_lazy_func(func.function, fields, args, kwargs)
        self.lazy_lookups.append((lazy_func, fields, args, kwargs))

    def register_lazy_func(self, func, keys):
        """
        DEPRECATED. Use `add_lazy_fields` instead.
        """
        warnings.warn(
            '`register_lazy_func` is deprecated. `add_lazy_fields` should be used instead. '
            'This plugin should be updated to work with the latest versions of FlexGet',
            DeprecationWarning,
            stacklevel=2,
        )
        super().register_lazy_func(func, keys, [], {})

    def __eq__(self, other):
        return self.get('original_title') == other.get('original_title') and self.get(
            'original_url'
        ) == other.get('original_url')

    def __hash__(self):
        return hash(self.get('original_title', '') + self.get('original_url', ''))

    def __repr__(self):
        return '<Entry(title={},state={})>'.format(self['title'], self._state)


lazy_func_registry = {}


class LazyFunc:
    def __init__(self, lazy_func_name: str):
        self.name = lazy_func_name
        self._func = None

    def __call__(self, func: Callable) -> Callable:
        if self.name in lazy_func_registry:
            raise Exception(
                f'The name {self.name} is already registered to another lazy function.'
            )
        func.lazy_func_id = self.name
        self._func = func
        lazy_func_registry[self.name] = self
        return func

    @property
    def function(self) -> Callable:
        if '.' in self._func.__qualname__:
            # This is a method of a plugin class, bind the function to the plugin instance
            plugin_class_name = self._func.__qualname__.split('.')[0]
            for p in plugin.plugins.values():
                if p.plugin_class.__name__ == plugin_class_name:
                    return types.MethodType(self._func, p.instance)
            raise Exception(
                f'lazy lookups must be functions, or methods of a registered plugin class. {self._func!r} is not'
            )
        return self._func


register_lazy_lookup = LazyFunc
