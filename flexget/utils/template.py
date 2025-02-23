import locale
import os
import os.path
import re
from collections.abc import Mapping
from contextlib import suppress
from copy import copy
from datetime import date, datetime, time
from typing import TYPE_CHECKING, Any, AnyStr, Optional, Union, cast
from unicodedata import normalize

import jinja2.filters
import pendulum
from jinja2 import (
    ChoiceLoader,
    Environment,
    FileSystemLoader,
    PackageLoader,
    StrictUndefined,
    Template,
    TemplateNotFound,
    TemplateSyntaxError,
)
from jinja2.nativetypes import NativeTemplate
from loguru import logger
from pendulum import DateTime
from pendulum import Interval as _Interval

from flexget.event import event
from flexget.utils.lazy_dict import LazyDict
from flexget.utils.pathscrub import pathscrub
from flexget.utils.tools import format_filesize, parse_filesize, split_title_year

if TYPE_CHECKING:
    from flexget.entry import Entry
    from flexget.manager import Manager
    from flexget.task import Task

logger = logger.bind(name='utils.template')

# The environment will be created after the manager has started
environment: Optional['FlexGetEnvironment'] = None


def extra_vars() -> dict:
    return {
        'timedelta': pendulum.duration,
        'duration': pendulum.duration,
        'utcnow': CoercingDateTime.utcnow(),
        'now': CoercingDateTime.now(),
    }


class RenderError(Exception):
    """Error raised when there is a problem with jinja rendering."""


class Interval(_Interval):
    """Same as normal Interval, but gives a better string representation for our templates."""

    def __str__(self):
        return self.in_words()


class CoercingDateTime(DateTime):
    """Datetime with some features that make it better when used in our templates.

    The features are:

    - Avoids crashing when comparing tz aware and naive datetimes.
      When this happens, it will assume the naive datetime is in the same timezone as the dt aware one.
    - Allows comparisons with plain dates, where the date is assumed to be at midnight in the same timezone.
    - Returns `Interval`s with a nicer string representation for our templates

    This allows us to introduce tz aware datetimes into entry fields without breaking old configs, or old plugins.
    """

    @staticmethod
    def _same_tz(first, second):
        if not isinstance(first, datetime) or not isinstance(second, date):
            raise TypeError(
                f'Cannot compare instances of {first.__class__.__name__} and {second.__class__.__name__}'
            )
        if not first or not second:
            return first, second
        if isinstance(second, date) and not isinstance(second, datetime):
            second = CoercingDateTime.create(
                second.year, second.month, second.day, tz=first.tzinfo
            )
        if first.tzinfo and not second.tzinfo:
            second = CoercingDateTime.instance(second, tz=first.tzinfo)
        elif not first.tzinfo and second.tzinfo:
            first = CoercingDateTime.instance(first, tz=second.tzinfo)
        return first, second

    def __lt__(self, other):
        self, other = self._same_tz(self, other)
        return DateTime.__lt__(self, other)

    def __le__(self, other):
        self, other = self._same_tz(self, other)
        return DateTime.__le__(self, other)

    def __gt__(self, other):
        self, other = self._same_tz(self, other)
        return DateTime.__gt__(self, other)

    def __ge__(self, other):
        self, other = self._same_tz(self, other)
        return DateTime.__ge__(self, other)

    def __eq__(self, other):
        # stdlib and pendulum dates and datetimes all subclass 'date'
        if not isinstance(other, date):
            return False
        self, other = self._same_tz(self, other)
        return DateTime.__eq__(self, other)

    def __ne__(self, other):
        if not isinstance(other, date):
            return True
        self, other = self._same_tz(self, other)
        return DateTime.__ne__(self, other)

    def __sub__(self, other):
        if isinstance(other, datetime):
            self, other = self._same_tz(self, other)
        return DateTime.__sub__(self, other)

    def diff(self, dt: Optional[datetime] = None, abs: bool = True) -> Interval:
        """Return the difference between two DateTime objects represented as an Interval."""
        if dt is None:
            dt = self.now(self.tz)

        return Interval(self, dt, absolute=abs)


def filter_pathbase(val: Optional[str]) -> str:
    """Return base name of a path."""
    return os.path.basename(val or '')


def filter_pathname(val: Optional[str]) -> str:
    """Return base name of a path, without its extension."""
    return os.path.splitext(os.path.basename(val or ''))[0]


def filter_pathext(val: Optional[str]) -> str:
    """Extension of a path (including the '.')."""
    return os.path.splitext(val or '')[1]


def filter_pathdir(val: Optional[str]) -> str:
    """Directory containing the given path."""
    return os.path.dirname(val or '')


def filter_pathscrub(val: str, os_mode: Optional[str] = None) -> str:
    """Replace problematic characters in a path."""
    if not isinstance(val, str):
        return val
    return pathscrub(val, os_mode)


def filter_re_replace(val: AnyStr, pattern: str, repl: str) -> str:
    """Perform a regexp replacement on the given string."""
    return re.sub(pattern, repl, str(val))


def filter_re_search(val, pattern: str):
    """Perform a search for given regexp pattern, return the matching portion of the text."""
    if not isinstance(val, str):
        return val
    result = re.search(pattern, val, re.IGNORECASE)
    if result:
        return result.group(0)
    return ''


def filter_formatdate(val, format_str):
    """Return a string representation of a datetime object according to format string."""
    if not isinstance(val, (datetime, date, time)):
        return val
    return val.strftime(format_str)


def filter_parsedate(val):
    """Attempt to parse a date according to the rules in ISO 8601 and RFC 2822."""
    return CoercingDateTime.instance(pendulum.parse(val, strict=False, tz=None))


def filter_date_suffix(date_str: str):
    """Return a date suffix for a given date."""
    day = int(date_str[-2:])
    suffix = 'th' if 4 <= day <= 20 or 24 <= day <= 30 else ['st', 'nd', 'rd'][day % 10 - 1]
    return date_str + suffix


def filter_format_number(val, places: Optional[int] = None, grouping: bool = True) -> str:
    """Format a number according to the user's locale."""
    if not isinstance(val, (int, float)):
        return val
    if places is not None:
        format_str = f'%.{places}f'
    elif isinstance(val, int):
        format_str = '%d'
    else:
        format_str = '%.02f'

    locale.setlocale(locale.LC_ALL, '')
    return locale.format_string(format_str, val, grouping)


def filter_pad(val: Union[int, str], width: int, fillchar: str = '0') -> str:
    """Pad a number or string with fillchar to the specified width."""
    return str(val).rjust(width, fillchar)


def filter_to_date(date_time_val):
    """Return the date from any date-time object."""
    if not isinstance(date_time_val, (datetime, date, time)):
        return date_time_val
    return date_time_val.date()


def filter_default(value, default_value: str = '', boolean: bool = True) -> str:
    """Override the built-in Jinja default filter to set the `boolean` param to True by default."""
    return jinja2.filters.do_default(value, default_value, boolean)


filter_d = filter_default


def filter_asciify(text: str) -> str:
    """Siplify text."""
    if not isinstance(text, str):
        return text

    result = normalize('NFD', text)
    result = result.encode('ascii', 'ignore')
    result = result.decode("utf-8")
    return str(result)


def filter_strip_symbols(text: str) -> str:
    """Strip Symbols text."""
    if not isinstance(text, str):
        return text

    # Symbols that should be converted to white space
    result = re.sub(r'[ \(\)\-_\[\]\.]+', ' ', text)
    # Leftovers
    result = re.sub(r"[^\w\d\s]", "", result)
    # Replace multiple white spaces with one
    return ' '.join(result.split())


def filter_strip_year(name: str) -> str:
    return split_title_year(name).title


def filter_get_year(name: str) -> str:
    return split_title_year(name).year


def filter_parse_size(val: str, si: bool = False, match_re: Optional[str] = None) -> int:
    """Parse human-readable file size to bytes."""
    if not isinstance(val, str):
        return val

    try:
        return parse_filesize(val, si=si, match_re=match_re)
    except ValueError:
        return 0


def filter_format_size(size: float, si=False, unit=None):
    if not isinstance(size, (int, float)):
        return size
    return format_filesize(size, si=si, unit=unit)


def is_fs_file(pathname: Union[str, os.PathLike]) -> bool:
    """Test whether item is existing file in filesystem."""
    return os.path.isfile(pathname)


def is_fs_dir(pathname: Union[str, os.PathLike]) -> bool:
    """Test whether item is existing directory in filesystem."""
    return os.path.isdir(pathname)


def is_fs_link(pathname: Union[str, os.PathLike]) -> bool:
    """Test whether item is existing link in filesystem."""
    return os.path.islink(pathname)


class FlexGetTemplate(Template):
    """Adds lazy lookup support when rendering templates."""

    def new_context(self, vars=None, shared=False, locals=None):
        context = super().new_context(vars, shared, locals)
        context.parent = LazyDict(context.parent)
        return context


class FlexGetNativeTemplate(FlexGetTemplate, NativeTemplate):
    """Lazy lookup support and native python return types."""


class FlexGetEnvironment(Environment):
    """Environment with template_class support."""

    template_class: type[FlexGetTemplate]


@event('manager.initialize')
def make_environment(manager: 'Manager') -> None:
    """Create our environment and add our custom filters."""
    global environment
    environment = FlexGetEnvironment(
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
    for name, test in list(globals().items()):
        if name.startswith('is_'):
            environment.tests[name.split('_', 1)[1]] = test


def list_templates(extensions: Optional[list[str]] = None) -> list[str]:
    """Return all templates names that are configured under environment loader dirs."""
    if environment is None or not hasattr(environment, 'loader'):
        return []
    return environment.list_templates(extensions=extensions)


def get_filters() -> dict:
    """Return all built-in and custom Jinja filters in a dict.

    The key is the name, and the value is the filter func
    """
    if environment is None or not hasattr(environment, 'loader'):
        return {}
    return environment.filters


def get_template(template_name: str, scope: Optional[str] = 'task') -> FlexGetTemplate:
    """Load a template from disk. Looks in both included plugins and users custom scope dir."""
    if not template_name.endswith('.template'):
        template_name += '.template'
    locations = []
    if scope:
        locations.append(scope + '/' + template_name)
    locations.append(template_name)
    for location in locations:
        if environment is not None:
            with suppress(TemplateNotFound):
                return cast(FlexGetTemplate, environment.get_template(location))
    err = f'Template not found in templates dir: {template_name}'
    if scope:
        err += f' ({scope})'
    raise ValueError(err)


def render(template: Union[FlexGetTemplate, str], context: Mapping, native: bool = False) -> str:
    """Render a Template with `context` as its context.

    :param template: Template or template string to render.
    :param context: Context to render the template from.
    :param native: If True, and the rendering result can be all native python types, not just strings.
    :return: The rendered template text.
    """
    if isinstance(template, str) and environment is not None:
        template_class = None
        if native:
            template_class = FlexGetNativeTemplate
        try:
            template = cast(
                FlexGetTemplate, environment.from_string(template, template_class=template_class)
            )
        except TemplateSyntaxError as e:
            raise RenderError(f'Error in template syntax: {e.message}')
    try:
        template = cast(FlexGetTemplate, template)
        result = template.render(context)
    except Exception as e:
        error = RenderError(f'({type(e).__name__}) {e}')
        logger.debug('Error during rendering: {}', error)
        raise error

    return result


def render_from_entry(
    template: Union[FlexGetTemplate, str], entry: 'Entry', native: bool = False
) -> str:
    """Render a Template or template string with an Entry as its context."""
    # Make a copy of the Entry so we can add some more fields
    variables = copy(entry.store)
    variables.update(extra_vars())
    # Add task name to variables, usually it's there because metainfo_task plugin, but not always
    if hasattr(entry, 'task') and entry.task is not None:
        if 'task' not in variables:
            variables['task'] = entry.task.name
        # Since `task` has different meaning between entry and task scope, the `task_name` field is create to be
        # consistent
        variables['task_name'] = entry.task.name
    return render(template, variables, native=native)


def render_from_task(template: Union[FlexGetTemplate, str], task: 'Task') -> str:
    """Render a Template with a task as its context.

    :param template: Template or template string to render.
    :param task: Task to render the template from.
    :return: The rendered template text.
    """
    variables = {'task': task, 'task_name': task.name}
    variables.update(extra_vars())
    return render(template, variables)


def evaluate_expression(expression: str, context: Mapping) -> Any:
    """Evaluate a jinja `expression` using a given `context` with support for `LazyDict`s (`Entry`s.).

    :param str expression:  A jinja expression to evaluate
    :param context: dictlike, supporting LazyDicts
    """
    if environment is not None:
        compiled_expr = environment.compile_expression(expression)
        # If we have a LazyDict, grab the underlying store. Our environment supports LazyFields directly
        if isinstance(context, LazyDict):
            context = context.store
        return compiled_expr(**{**context, **extra_vars()})
    return None
