"""
Provides small event framework
"""
from collections import defaultdict
from enum import Enum
from typing import Callable, Dict, List

from loguru import logger

logger = logger.bind(name='event')


class EventType(Enum):
    forget = 'forget'
    manager__before_config_validate = 'manager.before_config_validate'


_events: Dict[EventType, List[Callable]] = defaultdict(list)


class Event:
    """Represents one registered event."""

    def __init__(self, event_type: EventType, func: Callable, priority: int = 128):
        self.event_type = event_type
        self.name = event_type.value
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
        return (
            f'<Event(type={self.event_type},func={self.func.__name__},priority={self.priority})>'
        )

    __repr__ = __str__

    def __hash__(self):
        return hash((self.event_type, self.func, self.priority))


def event(event_type: EventType, priority: int = 128) -> Callable[[Callable], Callable]:
    """Register event to function with a decorator"""

    def decorator(func):
        add_event_handler(event_type, func, priority)
        return func

    return decorator


def get_events(event_type: EventType) -> List[Event]:
    """
    :param EventType event_type: event name
    :return: List of :class:`Event` for *name* ordered by priority
    """
    if event_type not in _events:
        raise KeyError(f'No such event {event_type}')
    _events[event_type].sort(reverse=True)
    return _events[event_type]


def add_event_handler(event_type: EventType, func: Callable, priority: int = 128) -> Event:
    """
    :param EventType event_type: Event type
    :param function func: Function that acts as event handler
    :param priority: Priority for this hook
    :return: Event created
    :rtype: Event
    :raises Exception: If *func* is already registered in an event
    """
    events = _events[event_type]
    for event_ in events:
        if event_.func == func:
            raise ValueError(
                f'{func.__name__} has already been registered as event listener under name {event_type}'
            )
    logger.trace('registered function {} to event {}', func.__name__, event_type)
    event_ = Event(event_type, func, priority)
    events.append(event_)
    return event_


def remove_event_handlers(event_type: EventType):
    """Removes all handlers for given event `event_type`."""
    _events.pop(event_type, None)


def remove_event_handler(event_type: EventType, func: Callable):
    """Remove `func` from the handlers for event `event_type`."""
    for e in _events[event_type]:
        if e.func is func:
            _events[event_type].remove(e)


def fire_event(event_type: EventType, *args, **kwargs):
    """
    Trigger an event with *name*. If event is not hooked by anything nothing happens. If a function that hooks an event
    returns a value, it will replace the first argument when calling next function.

    :param event_type: Type of event to be called
    :param args: List of arguments passed to handler function
    :param kwargs: Key Value arguments passed to handler function
    """
    if event_type in _events:
        for event in get_events(event_type):
            result = event(*args, **kwargs)
            if result is not None:
                args = (result,) + args[1:]
    return args and args[0]
