from datetime import datetime
from functools import update_wrapper
from sqlalchemy import extract
from sqlalchemy.orm import synonym
from flexget.feed import Entry
from flexget.manager import Session


def with_session(func):
    """"Creates a session if one was not passed via keyword argument to the function"""

    def wrapper(*args, **kwargs):
        if not kwargs.get('session'):
            kwargs['session'] = Session(autoflush=True)
            try:
                return func(*args, **kwargs)
            finally:
                kwargs['session'].close()
        else:
            return func(*args, **kwargs)
    return wrapper


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
            setattr(self, name, datetime.strptime(value, '%Y-%m-%d'))
        else:
            setattr(self, name, value)

    return synonym(name, descriptor=property(getter, setter))


def entry_synonym(name):
    """Used to store Entry instances into a PickleType column in the database.

    In order to ensure everything can be loaded after code changes, makes sure no custom python classes are pickled.
    """

    def only_builtins(item):
        """Casts all subclasses of builtin types to their builtin python type. Works recursively on iterables.

        Raises ValueError if passed an object that doesn't subclass a builtin type.
        """

        if type(item) in [str, unicode, int, float, bool]:
            return item
        elif isinstance(item, dict):
            result = {}
            for key, value in item.iteritems():
                try:
                    result[key] = only_builtins(value)
                except ValueError:
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
        elif isinstance(item, str):
            return str(item)
        elif isinstance(item, basestring):
            return unicode(item)
        elif isinstance(item, int):
            return int(item)
        elif isinstance(item, float):
            return float(item)
        elif isinstance(item, bool):
            return bool(item)

        # If item isn't a subclass of a builtin python type, raise ValueError.
        raise ValueError('%r is not a subclass of a builtin python type.' % type(item))

    def getter(self):
        return Entry(getattr(self, name))

    def setter(self, entry):
        setattr(self, name, only_builtins(entry))

    return synonym(name, descriptor=property(getter, setter))


class property_(object):
    """A property for an sqlalchemy model that can also return the proper sql to be used in queries."""

    def __init__(self, fget, fset=None, fdel=None, expr=None):
        self.fget = fget
        self.fset = fset
        self.fdel = fdel
        self.expr = expr or fget
        update_wrapper(self, fget)

    def __get__(self, instance, owner):
        if instance is None:
            return self.expr(owner)
        else:
            return self.fget(instance)

    def __set__(self, instance, value):
        self.fset(instance, value)

    def __delete__(self, instance):
        self.fdel(instance)

    def setter(self, fset):
        self.fset = fset
        return self

    def deleter(self, fdel):
        self.fdel = fdel
        return self

    def expression(self, expr):
        self.expr = expr
        return self


def year_property(date_attr):

    def getter(self):
        date = getattr(self, date_attr)
        return date and date.year

    def expr(cls):
        return extract('year', getattr(cls, date_attr))

    return property_(getter, expr=expr)
