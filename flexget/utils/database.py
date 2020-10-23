import functools
from datetime import datetime
from typing import List, Union, Optional, Any

from sqlalchemy import extract, func
from sqlalchemy.ext.hybrid import Comparator, hybrid_property
from sqlalchemy.orm import synonym, SynonymProperty

from flexget.entry import Entry
from flexget.manager import Session
from flexget.utils import json, qualities, serialization


def with_session(*args, **kwargs):
    """"
    A decorator which creates a new session if one was not passed via keyword argument to the function.

    Automatically commits and closes the session if one was created, caller is responsible for commit if passed in.

    If arguments are given when used as a decorator, they will automatically be passed to the created Session when
    one is not supplied.
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            if kwargs.get('session'):
                return func(*args, **kwargs)
            with _Session() as session:
                kwargs['session'] = session
                return func(*args, **kwargs)

        return wrapper

    if len(args) == 1 and not kwargs and callable(args[0]):
        # Used without arguments, e.g. @with_session
        # We default to expire_on_commit being false, in case the decorated function returns db instances
        _Session = functools.partial(Session, expire_on_commit=False)
        return decorator(args[0])
    else:
        # Arguments were specified, turn them into arguments for Session creation e.g. @with_session(autocommit=True)
        _Session = functools.partial(Session, *args, **kwargs)
        return decorator


def pipe_list_synonym(name: str) -> SynonymProperty:
    """Converts pipe separated text into a list"""

    def getter(self) -> Optional[List[str]]:
        attr = getattr(self, name)
        if attr:
            return attr.strip('|').split('|')
        return None

    def setter(self, value: Union[str, List[str]]) -> None:
        if isinstance(value, str):
            setattr(self, name, value)
        else:
            setattr(self, name, '|'.join(value))

    return synonym(name, descriptor=property(getter, setter))


def text_date_synonym(name: str) -> SynonymProperty:
    """Converts Y-M-D date strings into datetime objects"""

    def getter(self) -> Optional[datetime]:
        return getattr(self, name)

    def setter(self, value: Union[str, datetime]) -> None:
        if isinstance(value, str):
            try:
                setattr(self, name, datetime.strptime(value, '%Y-%m-%d'))
            except ValueError:
                # Invalid date string given, set to None
                setattr(self, name, None)
        else:
            setattr(self, name, value)

    return synonym(name, descriptor=property(getter, setter))


def entry_synonym(name: str) -> SynonymProperty:
    """Use serialization system to store Entries in db."""

    def getter(self) -> Any:
        return serialization.loads(getattr(self, name))

    def setter(self, entry: Union[dict, Entry]) -> None:
        if isinstance(entry, dict):
            if entry.get('serializer') == 'Entry' and 'version' in entry and 'value' in entry:
                # This is already a serialized form of entry
                setattr(self, name, json.dumps(entry))
                return
            entry = Entry(entry)
        if isinstance(entry, Entry):
            setattr(self, name, serialization.dumps(entry))
        else:
            raise TypeError(f'{type(entry)!r} is not type Entry or dict.')

    return synonym(name, descriptor=property(getter, setter))


def json_synonym(name: str) -> SynonymProperty:
    """Use json to serialize python objects for db storage."""

    def getter(self) -> Any:
        return json.loads(getattr(self, name), decode_datetime=True)

    def setter(self, entry: Any) -> None:
        setattr(self, name, json.dumps(entry, encode_datetime=True))

    return synonym(name, descriptor=property(getter, setter))


class CaseInsensitiveWord(Comparator):
    """Hybrid value representing a string that compares case insensitively."""

    def __init__(self, word: Union[str, 'CaseInsensitiveWord']):
        if isinstance(word, CaseInsensitiveWord):
            self.word: str = word.word
        else:
            self.word = word

    def lower(self) -> str:
        if isinstance(self.word, str):
            return self.word.lower()
        else:
            return func.lower(self.word)

    def operate(self, op, other):
        if not isinstance(other, CaseInsensitiveWord):
            other = CaseInsensitiveWord(other)
        return op(self.lower(), other.lower())

    def __clause_element__(self) -> str:
        return self.lower()

    def __str__(self) -> str:
        return self.word

    def __getattr__(self, item):
        """Expose string methods to be called directly on this object."""
        return getattr(self.word, item)


def quality_property(text_attr):
    def getter(self):
        return qualities.Quality(getattr(self, text_attr))

    def setter(self, value):
        if isinstance(value, str):
            setattr(self, text_attr, value)
        else:
            setattr(self, text_attr, value.name)

    class QualComparator(Comparator):
        def operate(self, op, other):
            if isinstance(other, qualities.Quality):
                other = other.name
            return op(self.__clause_element__(), other)

    def comparator(self):
        return QualComparator(getattr(self, text_attr))

    prop = hybrid_property(getter, setter)
    prop = prop.comparator(comparator)
    return prop


def quality_requirement_property(text_attr):
    def getter(self):
        return qualities.Requirements(getattr(self, text_attr))

    def setter(self, value):
        if isinstance(value, str):
            setattr(self, text_attr, value)
        else:
            setattr(self, text_attr, value.text)

    prop = hybrid_property(getter, setter)
    return prop


def ignore_case_property(text_attr):
    def getter(self):
        return CaseInsensitiveWord(getattr(self, text_attr))

    def setter(self, value):
        setattr(self, text_attr, value)

    return hybrid_property(getter, setter)


def year_property(date_attr):
    def getter(self):
        date = getattr(self, date_attr)
        return date and date.year

    def expr(cls):
        return extract('year', getattr(cls, date_attr))

    return hybrid_property(getter, expr=expr)
