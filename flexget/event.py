import logging

log = logging.getLogger('event')


_events = {}


class Event(object):

    def __init__(self, name, func, priority=128):
        self.name = name
        self.func = func
        self.priority = priority

    def __call__(self, *args, **kwargs):
        self.func(*args, **kwargs)

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
    """Return list of Events for :name: ordered by priority"""
    if not name in _events:
        raise KeyError('No such event %s' % name)
    _events[name].sort(reverse=True)
    return _events[name]


def add_event_handler(name, func, priority=128):
    """Attach event to :func: under a name :name: with :priority:. Returns Event created."""

    events = _events.setdefault(name, [])
    for event in events:
        if event.func == func:
            raise Exception('%s has already been registered as event listener under name %s' % (func.__name__, name))
    log.debug('registered function %s to event %s' % (func.__name__, name))
    event = Event(name, func, priority)
    events.append(event)
    return event


def remove_event_handler(name, func):
    # TODO: implement
    raise NotImplementedError


def fire_event(name, *args, **kwargs):
    """Trigger an event"""
    if not name in _events:
        log.debug('nothing registered for event %s' % name)
        return
    for event in get_events(name):
        log.debug('calling %s' % event)
        event(*args, **kwargs)
