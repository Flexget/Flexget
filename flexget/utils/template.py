import logging
import os
import re
import sys
from copy import copy
from datetime import datetime, date, time
from email.utils import parsedate
from time import mktime
from jinja2 import Environment, StrictUndefined, PackageLoader

log = logging.getLogger('utils.template')


def filter_pathbase(val):
    """Base name of a path."""
    return os.path.basename(val or '')


def filter_pathname(val):
    """Base name of a path, without its extension."""
    return os.path.splitext(os.path.basename(val or ''))[0]


def filter_pathext(val):
    """Extension of a path (including the '.')."""
    return os.path.splitext(val or '')[1]


def filter_pathdir(val):
    """Directory containing the given path."""
    return os.path.dirname(val or '')


def filter_pathscrub(val, ascii=False, windows=None):
    """Replace problematic characters in a path."""
    if windows is None:
        windows = sys.platform.startswith("win")
    if ascii:
        repl = {'"': '`', "'": '`'}
        if windows:
            repl.update({':': ';', '?': '_'})
    else:
        repl = {'"': u'\u201d', "'": u'\u2019'}
        if windows:
            repl.update({':': u'\u02d0', '?': u'\u061f'})

    return re.sub('[%s]' % ''.join(repl), lambda i: repl[i.group(0)], val or '')


def filter_re_replace(val, pattern, repl):
    """Perform a regexp replacement on the given string."""
    return re.sub(pattern, repl, unicode(val))


def filter_re_search(val, pattern):
    """Perform a search for given regexp pattern, return the matching portion of the text."""
    if not isinstance(val, basestring):
        return val
    result = re.search(pattern, val)
    if result:
        i = result.group(0)
        return result.group(0)
    return ''


def filter_formatdate(val, format):
    """Returns a string representation of a datetime object according to format string."""
    if not isinstance(val, (datetime, date, time)):
        return val
    return val.strftime(format)


def filter_parsedate(val):
    """Attempts to parse a date according to the rules in RFC 2822"""
    return datetime.fromtimestamp(mktime(parsedate(val)))


# Create our environment and add our custom filters
# TODO: Add a filesystem loader for config_base direcotry
environment = Environment(undefined=StrictUndefined, loader=PackageLoader('flexget'))
for name, filt in globals().items():
    if name.startswith('filter_'):
        environment.filters[name.split('_', 1)[1]] = filt


def get_template(name):
    return environment.get_template(name)


def render_from_entry(template, entry):
    """Renders a Template or template string with an Entry as its context."""

    # If a plain string was passed, turn it into a Template
    if isinstance(template, basestring):
        template = environment.from_string(template)
    # Make a copy of the Entry so we can add some more fields
    variables = copy(entry)
    variables['now'] = datetime.now()
    # We use the lower level render function, so that our Entry is not cast into a dict (and lazy loading lost)
    try:
        return u''.join(template.root_render_func(template.new_context(variables)))
    except:
        exc_info = sys.exc_info()
    return environment.handle_exception(exc_info, True)
