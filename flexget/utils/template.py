from __future__ import unicode_literals, division, absolute_import
from future.utils import text_to_native_str
from flexget.utils.tools import native_str_to_text
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import os
import re
import locale
from copy import copy
from datetime import datetime, date, time

import jinja2.filters
from jinja2 import (
    Environment,
    StrictUndefined,
    ChoiceLoader,
    FileSystemLoader,
    PackageLoader,
    Template,
    TemplateNotFound,
    TemplateSyntaxError,
)
from jinja2.nativetypes import NativeTemplate
from dateutil import parser as dateutil_parse

from flexget.event import event
from flexget.utils.lazy_dict import LazyDict
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
    return re.sub(pattern, repl, str(val))


def filter_re_search(val, pattern):
    """Perform a search for given regexp pattern, return the matching portion of the text."""
    if not isinstance(val, str):
        return val
    result = re.search(pattern, val, re.IGNORECASE)
    if result:
        return result.group(0)
    return ''


def filter_formatdate(val, format):
    """Returns a string representation of a datetime object according to format string."""
    encoding = locale.getpreferredencoding()
    if not isinstance(val, (datetime, date, time)):
        return val
    return native_str_to_text(
        val.strftime(text_to_native_str(format, encoding=encoding)), encoding=encoding
    )


def filter_parsedate(val):
    """Attempts to parse a date according to the rules in ISO 8601 and RFC 2822"""
    return dateutil_parse.parse(val)


def filter_date_suffix(date):
    """Returns a date suffix for a given date"""
    day = int(date[-2:])
    if 4 <= day <= 20 or 24 <= day <= 30:
        suffix = "th"
    else:
        suffix = ["st", "nd", "rd"][day % 10 - 1]
    return date + suffix


def filter_format_number(val, places=None, grouping=True):
    """Formats a number according to the user's locale."""
    if not isinstance(val, (int, float, int)):
        return val
    if places is not None:
        format = '%.' + str(places) + 'f'
    elif isinstance(val, (int, int)):
        format = '%d'
    else:
        format = '%.02f'

    locale.setlocale(locale.LC_ALL, '')
    return locale.format(format, val, grouping)


def filter_pad(val, width, fillchar='0'):
    """Pads a number or string with fillchar to the specified width."""
    return str(val).rjust(width, fillchar)


def filter_to_date(date_time_val):
    """Returns the date from any date-time object"""
    if not isinstance(date_time_val, (datetime, date, time)):
        return date_time_val
    return date_time_val.date()


def filter_default(value, default_value='', boolean=True):
    """Override the built-in Jinja default filter to change the `boolean` param to True by default"""
    return jinja2.filters.do_default(value, default_value, boolean)


filter_d = filter_default


class FlexGetTemplate(Template):
    """Adds lazy lookup support when rendering templates."""

    def new_context(self, vars=None, shared=False, locals=None):
        context = super(FlexGetTemplate, self).new_context(vars, shared, locals)
        context.parent = LazyDict(context.parent)
        return context


class FlexGetNativeTemplate(FlexGetTemplate, NativeTemplate):
    """Lazy lookup support and native python return types."""
    pass


@event('manager.initialize')
def make_environment(manager):
    """Create our environment and add our custom filters"""
    global environment
    environment = Environment(
        undefined=StrictUndefined,
        loader=ChoiceLoader(
            [
                PackageLoader('flexget'),
                FileSystemLoader(os.path.join(manager.config_base, 'templates')),
            ]
        ),
        extensions=['jinja2.ext.loopcontrols'],
    )
    environment.template_class = FlexGetTemplate
    for name, filt in list(globals().items()):
        if name.startswith('filter_'):
            environment.filters[name.split('_', 1)[1]] = filt


def list_templates(extensions=None):
    """
    Returns all templates names that are configured under environment loader dirs
    """
    if environment is None or not hasattr(environment, 'loader'):
        return
    return environment.list_templates(extensions=extensions)


def get_filters():
    """
    Returns all built-in and custom Jinja filters in a dict, where the key is the name, and the value is the filter func
    """
    if environment is None or not hasattr(environment, 'loader'):
        return {}
    return environment.filters.items()


def get_template(template_name, scope='task'):
    """Loads a template from disk. Looks in both included plugins and users custom scope dir."""

    if not template_name.endswith('.template'):
        template_name += '.template'
    locations = []
    if scope:
        locations.append(scope + '/' + template_name)
    locations.append(template_name)
    for location in locations:
        try:
            return environment.get_template(location)
        except TemplateNotFound:
            pass
    else:
        if scope:
            err = 'Template not found in templates dir: %s (%s)' % (template_name, scope)
        else:
            err = 'Template not found in templates dir: %s' % template_name
        raise ValueError(err)


def render(template, context, native=False):
    """
    Renders a Template with `context` as its context.

    :param template: Template or template string to render.
    :param context: Context to render the template from.
    :param native: If True, and the rendering result can be all native python types, not just strings.
    :return: The rendered template text.
    """
    if isinstance(template, str):
        template_class = None
        if native:
            template_class = FlexGetNativeTemplate
        try:
            template = environment.from_string(template, template_class=template_class)
        except TemplateSyntaxError as e:
            raise RenderError('Error in template syntax: ' + e.message)
    try:
        result = template.render(context)
    except Exception as e:
        error = RenderError('(%s) %s' % (type(e).__name__, e))
        log.debug('Error during rendering: %s', error)
        raise error

    return result


def render_from_entry(template_string, entry, native=False):
    """Renders a Template or template string with an Entry as its context."""

    # Make a copy of the Entry so we can add some more fields
    variables = copy(entry.store)
    variables['now'] = datetime.now()
    # Add task name to variables, usually it's there because metainfo_task plugin, but not always
    if hasattr(entry, 'task') and entry.task is not None:
        if 'task' not in variables:
            variables['task'] = entry.task.name
        # Since `task` has different meaning between entry and task scope, the `task_name` field is create to be
        # consistent
        variables['task_name'] = entry.task.name
    return render(template_string, variables, native=native)


def render_from_task(template, task):
    """
    Renders a Template with a task as its context.

    :param template: Template or template string to render.
    :param task: Task to render the template from.
    :return: The rendered template text.
    """
    variables = {'task': task, 'now': datetime.now(), 'task_name': task.name}
    return render(template, variables)


def evaluate_expression(expression, context):
    """
    Evaluate a jinja `expression` using a given `context` with support for `LazyDict`s (`Entry`s.)

    :param str expression:  A jinja expression to evaluate
    :param context: dictlike, supporting LazyDicts
    """
    compiled_expr = environment.compile_expression(expression)
    # If we have a LazyDict, grab the underlying store. Our environment supports LazyFields directly
    if isinstance(context, LazyDict):
        context = context.store
    return compiled_expr(**context)
