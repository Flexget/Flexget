"""
Provides small event framework
"""
from __future__ import absolute_import, division, unicode_literals

import logging

log = logging.getLogger('event')

_events = {}


class Event(object):
    """Represents one registered event."""

    def __init__(self, name, func, priority=128):
        self.name = name
        self.func = func
        self.priority = priority

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)

    def __eq__(self, other):
        return self.priority == other.priority

    def __lt__(self, other):
        return self.priority < other.priority

    def __gt__(self, other):
        return self.priority > other.priority

    def __str__(self):
        return '<Event(name=%s,func=%s,priority=%s)>' % (self.name, self.func.__name__, self.priority)

    __repr__ = __str__


def event(name, priority=128):
    """Register event to function with a decorator"""

    def decorator(func):
        add_event_handler(name, func, priority)
        return func

    return decorator


def get_events(name):
    """
    :param String name: event name
    :return: List of :class:`Event` for *name* ordered by priority
    """
    if name not in _events:
        raise KeyError('No such event %s' % name)
    _events[name].sort(reverse=True)
    return _events[name]


def add_event_handler(name, func, priority=128):
    """
    :param string name: Event name
    :param function func: Function that acts as event handler
    :param priority: Priority for this hook
    :return: Event created
    :rtype: Event
    :raises Exception: If *func* is already registered in an event
    """
    events = _events.setdefault(name, [])
    for event in events:
        if event.func == func:
            raise ValueError('%s has already been registered as event listener under name %s' % (func.__name__, name))
    log.trace('registered function %s to event %s' % (func.__name__, name))
    event = Event(name, func, priority)
    events.append(event)
    return event


def remove_event_handlers(name):
    """Removes all handlers for given event `name`."""
    _events.pop(name, None)


def remove_event_handler(name, func):
    """Remove `func` from the handlers for event `name`."""
    for e in list(_events.get(name, [])):
        if e.func is func:
            _events[name].remove(e)


def fire_event(name, *args, **kwargs):
    """
    Trigger an event with *name*. If event is not hooked by anything nothing happens. If a function that hooks an event
    returns a value, it will replace the first argument when calling next function.

    :param name: Name of event to be called
    :param args: List of arguments passed to handler function
    :param kwargs: Key Value arguments passed to handler function
    """
    if name not in _events:
        return
    for event in get_events(name):
        result = event(*args, **kwargs)
        if result is not None:
            args = (result,) + args[1:]
    return args and args[0]
