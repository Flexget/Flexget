from __future__ import unicode_literals, division, absolute_import
import logging
import os
import re
import sys
from copy import copy
from datetime import datetime, date, time
import locale
from email.utils import parsedate
from time import mktime

from jinja2 import (Environment, StrictUndefined, ChoiceLoader,
                    FileSystemLoader, PackageLoader, TemplateNotFound,
                    TemplateSyntaxError, Undefined)

from flexget.event import event
from flexget.utils.pathscrub import pathscrub

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


def filter_pathscrub(val, os_mode=None):
    """Replace problematic characters in a path."""
    return pathscrub(val, os_mode)


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
    encoding = locale.getpreferredencoding()
    if not isinstance(val, (datetime, date, time)):
        return val
    return val.strftime(format.encode(encoding)).decode(encoding)


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
    return unicode(val).rjust(width, fillchar)


# Override the built-in Jinja default filter due to Jinja bug
# https://github.com/mitsuhiko/jinja2/pull/138
def filter_default(value, default_value=u'', boolean=False):
    if isinstance(value, Undefined) or (boolean and not value):
        return default_value
    return value


filter_d = filter_default


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
    """Loads a template from disk. Looks in both included plugins and users custom plugin dir."""

    if not templatename.endswith('.template'):
        templatename += '.template'
    locations = []
    if pluginname:
        locations.append(pluginname + '/' + templatename)
    locations.append(templatename)
    for location in locations:
        try:
            return environment.get_template(location)
        except TemplateNotFound:
            pass
    else:
        # TODO: Plugins need to catch and reraise this as PluginError, or perhaps we should have
        # a validator for template files
        raise ValueError('Template not found: %s (%s)' % (templatename, pluginname))


def render(template, context):
    """
    Renders a Template with `context` as its context.

    :param template: Template or template string to render.
    :param context: Context to render the template from.
    :return: The rendered template text.
    """
    if isinstance(template, basestring):
        template = environment.from_string(template)
    try:
        result = template.render(context)
    except Exception as e:
        raise RenderError('(%s) %s' % (type(e).__name__, e))

    return result


def render_from_entry(template_string, entry):
    """Renders a Template or template string with an Entry as its context."""

    # If a plain string was passed, turn it into a Template
    if isinstance(template_string, basestring):
        try:
            template = environment.from_string(template_string)
        except TemplateSyntaxError as e:
            raise RenderError('Error in template syntax: ' + e.message)
    else:
        # We can also support an actual Template being passed in
        template = template_string
    # Make a copy of the Entry so we can add some more fields
    variables = copy(entry)
    variables['now'] = datetime.now()
    # Add task name to variables, usually it's there because metainfo_task plugin, but not always
    if 'task' not in variables and hasattr(entry, 'task'):
        variables['task'] = entry.task.name
    # We use the lower level render function, so that our Entry is not cast into a dict (and lazy loading lost)
    try:
        result = u''.join(template.root_render_func(template.new_context(variables, shared=True)))
    except:
        exc_info = sys.exc_info()
        try:
            return environment.handle_exception(exc_info, True)
        except Exception as e:
            error = RenderError('(%s) %s' % (type(e).__name__, e))
            log.debug('Error during rendering: %s' % error)
            raise error

    # Only try string replacement if jinja didn't do anything
    if result == template_string:
        try:
            result = template_string % entry
        except KeyError as e:
            raise RenderError('Does not contain the field `%s` for string replacement.' % e)
        except ValueError as e:
            raise RenderError('Invalid string replacement template: %s (%s)' % (template_string, e))
        except TypeError as e:
            raise RenderError('Error during string replacement: %s' % e.message)

    return result


def render_from_task(template, task):
    """
    Renders a Template with a task as its context.

    :param template: Template or template string to render.
    :param task: Task to render the template from.
    :return: The rendered template text.
    """
    if isinstance(template, basestring):
        template = environment.from_string(template)
    try:
        result = template.render({'task': task})
    except Exception as e:
        raise RenderError('(%s) %s' % (type(e).__name__, e))

    return result
