import logging
import os
import re
import sys
from copy import copy
from datetime import datetime, date, time
import locale
from email.utils import parsedate
from time import mktime
from jinja2 import Environment, StrictUndefined, ChoiceLoader, FileSystemLoader, PackageLoader, TemplateNotFound
from flexget.event import event
from flexget.plugin import PluginError

log = logging.getLogger('utils.template')

# The environment will be created after the manager has started
environment = None


class RenderError(Exception):
    """Error raised when there is a problem with jinja rendering."""
    pass


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


def filter_format_number(val, places=None, grouping=True):
    """Formats a number according to the user's locale."""
    if not isinstance(val, (int, float, long)):
        return val
    if places is not None:
        format = '%.' + str(places) + 'f'
    elif isinstance(val, (int, long)):
        format = '%d'
    else:
        format = '%.02f'

    locale.setlocale(locale.LC_ALL, '')
    return locale.format(format, val, grouping)


def filter_pad(val, width, fillchar='0'):
    """Pads a number or string with fillchar to the specified width."""
    return str(val).rjust(width, fillchar)


@event('manager.startup')
def make_environment(manager):
    """Create our environment and add our custom filters"""
    global environment
    environment = Environment(undefined=StrictUndefined,
        loader=ChoiceLoader([PackageLoader('flexget'),
                             FileSystemLoader(os.path.join(manager.config_base, 'templates'))]),
        extensions=['jinja2.ext.loopcontrols'])
    for name, filt in globals().items():
        if name.startswith('filter_'):
            environment.filters[name.split('_', 1)[1]] = filt


# TODO: list_templates function


def get_template(templatename, pluginname=None):

    if pluginname is not None:
        try:
            return environment.get_template(pluginname + '/' + templatename)
        except TemplateNotFound:
            pass
    try:
        return environment.get_template(templatename)
    except TemplateNotFound, e:
        raise PluginError('Template not found: %s (%s)' % (e, pluginname))


def render_from_entry(template_string, entry):
    """Renders a Template or template string with an Entry as its context."""

    # If a plain string was passed, turn it into a Template
    if isinstance(template_string, basestring):
        template = environment.from_string(template_string)
    else:
        # We can also support an actual Template being passed in
        template = template_string
    # Make a copy of the Entry so we can add some more fields
    variables = copy(entry)
    variables['now'] = datetime.now()
    # We use the lower level render function, so that our Entry is not cast into a dict (and lazy loading lost)
    try:
        result = u''.join(template.root_render_func(template.new_context(variables)))
    except:
        exc_info = sys.exc_info()
        try:
            return environment.handle_exception(exc_info, True)
        except Exception, e:
            error = RenderError('(%s) %s' % (type(e).__name__, e))
            log.debug('Error during rendering: %s' % error)
            raise error

    # Only try string replacement if jinja didn't do anything
    if result == template_string:
        try:
            result = template_string % entry
        except KeyError, e:
            raise RenderError('Does not contain the field `%s` for string replacement.' % e)
        except ValueError, e:
            raise PluginError('Invalid string replacement template: %s (%s)' % (template_string, e))

    return result


def render_from_feed(template, feed):
    """
    Renders a Template with a feed as its context.

    :param template: Template or template string to render.
    :param feed: Feed to render the template from.
    :return: The rendered template text.
    """
    if isinstance(template, basestring):
        template = environment.from_string(template)
    try:
        result = template.render({'feed': feed})
    except Exception, e:
        raise RenderError('(%s) %s' % (type(e).__name__, e))

    return result
