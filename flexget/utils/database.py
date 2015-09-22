from __future__ import unicode_literals, division, absolute_import
import functools
from collections import Mapping
from datetime import datetime

from sqlalchemy import extract, func
from sqlalchemy.orm import synonym
from sqlalchemy.ext.hybrid import Comparator, hybrid_property

from flexget.manager import Session
from flexget.utils import qualities


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


def pipe_list_synonym(name):
    """Converts pipe separated text into a list"""

    def getter(self):
        attr = getattr(self, name)
        if attr:
            return attr.strip('|').split('|')

    def setter(self, value):
        if isinstance(value, basestring):
            setattr(self, name, value)
        else:
            setattr(self, name, '|'.join(value))

    return synonym(name, descriptor=property(getter, setter))


def text_date_synonym(name):
    """Converts Y-M-D date strings into datetime objects"""

    def getter(self):
        return getattr(self, name)

    def setter(self, value):
        if isinstance(value, basestring):
            try:
                setattr(self, name, datetime.strptime(value, '%Y-%m-%d'))
            except ValueError:
                # Invalid date string given, set to None
                setattr(self, name, None)
        else:
            setattr(self, name, value)

    return synonym(name, descriptor=property(getter, setter))


def safe_pickle_synonym(name):
    """Used to store Entry instances into a PickleType column in the database.

    In order to ensure everything can be loaded after code changes, makes sure no custom python classes are pickled.
    """

    def only_builtins(item):
        """Casts all subclasses of builtin types to their builtin python type. Works recursively on iterables.

        Raises ValueError if passed an object that doesn't subclass a builtin type.
        """

        supported_types = [str, unicode, int, float, long, bool, datetime]
        # dict, list, tuple and set are also supported, but handled separately

        if type(item) in supported_types:
            return item
        elif isinstance(item, Mapping):
            result = {}
            for key, value in item.iteritems():
                try:
                    result[key] = only_builtins(value)
                except TypeError:
                    continue
            return result
        elif isinstance(item, (list, tuple, set)):
            result = []
            for value in item:
                try:
                    result.append(only_builtins(value))
                except ValueError:
                    continue
            if isinstance(item, list):
                return result
            elif isinstance(item, tuple):
                return tuple(result)
            else:
                return set(result)
        else:
            for s_type in supported_types:
                if isinstance(item, s_type):
                    return s_type(item)

        # If item isn't a subclass of a builtin python type, raise ValueError.
        raise TypeError('%r is not a subclass of a builtin python type.' % type(item))

    def getter(self):
        return getattr(self, name)

    def setter(self, entry):
        setattr(self, name, only_builtins(entry))

    return synonym(name, descriptor=property(getter, setter))


class CaseInsensitiveWord(Comparator):
    """Hybrid value representing a string that compares case insensitively."""

    def __init__(self, word):
        if isinstance(word, CaseInsensitiveWord):
            self.word = word.word
        else:
            self.word = word

    def lower(self):
        if isinstance(self.word, basestring):
            return self.word.lower()
        else:
            return func.lower(self.word)

    def operate(self, op, other):
        if not isinstance(other, CaseInsensitiveWord):
            other = CaseInsensitiveWord(other)
        return op(self.lower(), other.lower())

    def __clause_element__(self):
        return self.lower()

    def __str__(self):
        return self.word

    def __getattr__(self, item):
        """Expose string methods to be called directly on this object."""
        return getattr(self.word, item)


def quality_property(text_attr):

    def getter(self):
        return qualities.Quality(getattr(self, text_attr))

    def setter(self, value):
        if isinstance(value, basestring):
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
    prop.comparator(comparator)
    return prop


def quality_requirement_property(text_attr):

    def getter(self):
        return qualities.Requirements(getattr(self, text_attr))

    def setter(self, value):
        if isinstance(value, basestring):
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
