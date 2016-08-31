from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from future.utils import PY2, native_str, text_type

import copy
import functools
import logging

from flexget.plugin import PluginError
from flexget.utils.lazy_dict import LazyDict, LazyLookup
from flexget.utils.template import render_from_entry

log = logging.getLogger('entry')


class EntryUnicodeError(Exception):
    """This exception is thrown when trying to set non-unicode compatible field value to entry."""

    def __init__(self, key, value):
        self.key = key
        self.value = value

    def __str__(self):
        return 'Entry strings must be unicode: %s (%r)' % (self.key, self.value)


class Entry(LazyDict):
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
        super(Entry, self).__init__()
        self.traces = []
        self.snapshots = {}
        self._state = 'undecided'
        self._hooks = {'accept': [], 'reject': [], 'fail': [], 'complete': []}
        self.task = None

        if len(args) == 2:
            kwargs['title'] = args[0]
            kwargs['url'] = args[1]
            args = []

        # Make sure constructor does not escape our __setitem__ enforcement
        self.update(*args, **kwargs)

    def trace(self, message, operation=None, plugin=None):
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

    def run_hooks(self, action, **kwargs):
        """
        Run hooks that have been registered for given ``action``.

        :param action: Name of action to run hooks for
        :param kwargs: Keyword arguments that should be passed to the registered functions
        """
        for func in self._hooks[action]:
            func(self, **kwargs)

    def add_hook(self, action, func, **kwargs):
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

    def on_accept(self, func, **kwargs):
        """
        Register a function to be called when this entry is accepted.

        :param func: The function to call
        :param kwargs: Keyword arguments that should be passed to the registered function
        """
        self.add_hook('accept', func, **kwargs)

    def on_reject(self, func, **kwargs):
        """
        Register a function to be called when this entry is rejected.

        :param func: The function to call
        :param kwargs: Keyword arguments that should be passed to the registered function
        """
        self.add_hook('reject', func, **kwargs)

    def on_fail(self, func, **kwargs):
        """
        Register a function to be called when this entry is failed.

        :param func: The function to call
        :param kwargs: Keyword arguments that should be passed to the registered function
        """
        self.add_hook('fail', func, **kwargs)

    def on_complete(self, func, **kwargs):
        """
        Register a function to be called when a :class:`Task` has finished processing this entry.

        :param func: The function to call
        :param kwargs: Keyword arguments that should be passed to the registered function
        """
        self.add_hook('complete', func, **kwargs)

    def accept(self, reason=None, **kwargs):
        if self.rejected:
            log.debug('tried to accept rejected %r' % self)
        elif not self.accepted:
            self._state = 'accepted'
            self.trace(reason, operation='accept')
            # Run entry on_accept hooks
            self.run_hooks('accept', reason=reason, **kwargs)

    def reject(self, reason=None, **kwargs):
        # ignore rejections on immortal entries
        if self.get('immortal'):
            reason_str = '(%s)' % reason if reason else ''
            log.info('Tried to reject immortal %s %s' % (self['title'], reason_str))
            self.trace('Tried to reject immortal %s' % reason_str)
            return
        if not self.rejected:
            self._state = 'rejected'
            self.trace(reason, operation='reject')
            # Run entry on_reject hooks
            self.run_hooks('reject', reason=reason, **kwargs)

    def fail(self, reason=None, **kwargs):
        log.debug('Marking entry \'%s\' as failed' % self['title'])
        if not self.failed:
            self._state = 'failed'
            self.trace(reason, operation='fail')
            log.error('Failed %s (%s)' % (self['title'], reason))
            # Run entry on_fail hooks
            self.run_hooks('fail', reason=reason, **kwargs)

    def complete(self, **kwargs):
        # Run entry on_complete hooks
        self.run_hooks('complete', **kwargs)

    @property
    def state(self):
        return self._state

    @property
    def accepted(self):
        return self._state == 'accepted'

    @property
    def rejected(self):
        return self._state == 'rejected'

    @property
    def failed(self):
        return self._state == 'failed'

    @property
    def undecided(self):
        return self._state == 'undecided'

    def __setitem__(self, key, value):
        # Enforce unicode compatibility.
        if PY2 and isinstance(value, native_str):
            # Allow Python 2's implicit string decoding, but fail now instead of when entry fields are used.
            # If encoding is anything but ascii, it should be decoded it to text before setting an entry field
            try:
                value = value.decode('ascii')
            except UnicodeDecodeError:
                raise EntryUnicodeError(key, value)
        elif isinstance(value, bytes):
            raise EntryUnicodeError(key, value)
        # Coerce any enriched strings (such as those returned by BeautifulSoup) to plain strings to avoid serialization
        # troubles.
        elif isinstance(value, text_type) and type(value) != text_type:  # pylint: disable=unidiomatic-typecheck
            value = text_type(value)

        # url and original_url handling
        if key == 'url':
            if not isinstance(value, (str, LazyLookup)):
                raise PluginError('Tried to set %r url to %r' % (self.get('title'), value))
            self.setdefault('original_url', value)

        # title handling
        if key == 'title':
            if not isinstance(value, (str, LazyLookup)):
                raise PluginError('Tried to set title to %r' % value)

        try:
            log.trace('ENTRY SET: %s = %r' % (key, value))
        except Exception as e:
            log.debug('trying to debug key `%s` value threw exception: %s' % (key, e))

        super(Entry, self).__setitem__(key, value)

    def safe_str(self):
        return '%s | %s' % (self['title'], self['url'])

    # TODO: this is too manual, maybe we should somehow check this internally and throw some exception if
    # application is trying to operate on invalid entry
    def isvalid(self):
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

    def take_snapshot(self, name):
        """
        Takes a snapshot of the entry under *name*. Snapshots can be accessed via :attr:`.snapshots`.
        :param string name: Snapshot name
        """
        snapshot = {}
        for field, value in self.items():
            try:
                snapshot[field] = copy.deepcopy(value)
            except TypeError:
                log.warning('Unable to take `%s` snapshot for field `%s` in `%s`' % (name, field, self['title']))
        if snapshot:
            if name in self.snapshots:
                log.warning('Snapshot `%s` is being overwritten for `%s`' % (name, self['title']))
            self.snapshots[name] = snapshot

    def update_using_map(self, field_map, source_item, ignore_none=False):
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

    def render(self, template):
        """
        Renders a template string based on fields in the entry.

        :param string template: A template string that uses jinja2 or python string replacement format.
        :return: The result of the rendering.
        :rtype: string
        :raises RenderError: If there is a problem.
        """
        if not isinstance(template, str):
            raise ValueError('Trying to render non string template, got %s' % repr(template))
        log.trace('rendering: %s' % template)
        return render_from_entry(template, self)

    def __eq__(self, other):
        return self.get('title') == other.get('title') and self.get('original_url') == other.get('original_url')

    def __hash__(self):
        return hash(self.get('title', '') + self.get('original_url', ''))

    def __repr__(self):
        return '<Entry(title=%s,state=%s)>' % (self['title'], self._state)
