from datetime import datetime
from functools import update_wrapper
from sqlalchemy import extract, func, case
from sqlalchemy.orm import synonym
from flexget.manager import Session
from flexget.utils import qualities


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


def safe_pickle_synonym(name):
    """Used to store Entry instances into a PickleType column in the database.

    In order to ensure everything can be loaded after code changes, makes sure no custom python classes are pickled.
    """

    def only_builtins(item):
        """Casts all subclasses of builtin types to their builtin python type. Works recursively on iterables.

        Raises ValueError if passed an object that doesn't subclass a builtin type.
        """

        supported_types = [str, unicode, int, float, bool, datetime]
        # dict, list, tuple and set are also supported, but handled separately

        if type(item) in supported_types:
            return item
        elif isinstance(item, dict):
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


def quality_synonym(name):
    """Get and set property as Quality objects, store as text in the database."""

    def getter(self):
        return qualities.get(getattr(self, name))

    def setter(self, value):
        if isinstance(value, basestring):
            setattr(self, name, value)
        else:
            setattr(self, name, value.name)

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


def lower_property(str_attr):
    """A property based on a text column that returns or queries on the lower case version of the string."""

    def getter(self):
        string = getattr(self, str_attr)
        return string and string.lower()

    def expr(cls):
        return func.lower(getattr(cls, str_attr))

    return property_(getter, expr=expr)


def quality_comp_property(str_attr):
    """Returns the value for the quality stored, which can be filtered against or used to sort queries."""

    def getter(self):
        return qualities.get(getattr(self, str_attr)).value

    def expr(cls):
        whens = {}
        for qual in qualities.all():
            whens[qual.name] = qual.value
        return case(value=getattr(cls, str_attr), whens=whens)

    return property_(getter, expr=expr)
