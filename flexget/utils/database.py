from datetime import datetime
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
    """Sanitizes entries before storing them to database, so they can be loaded again even after code changes."""

    def getter(self):
        return Entry(getattr(self, name))

    def setter(self, entry):
        entry_fields = {}
        for field, value in entry.iteritems():
            if isinstance(value, (basestring, bool, int, float, list, dict)):
                entry_fields[field] = value
        setattr(self, name, entry_fields)

    return synonym(name, descriptor=property(getter, setter))
