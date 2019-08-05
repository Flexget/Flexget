from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.error import HTTPError, URLError
from future.utils import python_2_unicode_compatible

import logging
import os
import re
import time
import pkg_resources
from functools import total_ordering
from http.client import BadStatusLine
from importlib import import_module

from path import Path
from requests import RequestException

from flexget import plugins as plugins_pkg
from flexget import components as components_pkg
from flexget import config_schema
from flexget.event import add_event_handler as add_phase_handler
from flexget.event import fire_event, remove_event_handlers

log = logging.getLogger('plugin')

PRIORITY_DEFAULT = 128
PRIORITY_LAST = -255
PRIORITY_FIRST = 255


@python_2_unicode_compatible
class DependencyError(Exception):
    """Plugin depends on other plugin, but it cannot be loaded.

    Args:
        issued_by: name of the plugin trying to do the import
        missing: name of the plugin or library that is missing
        message: customized user readable error message

    All args are optional.
    """

    def __init__(self, issued_by=None, missing=None, message=None, silent=False):
        super(DependencyError, self).__init__()
        self.issued_by = issued_by
        self.missing = missing
        self._message = message
        self.silent = silent

    def _get_message(self):
        if self._message:
            return self._message
        else:
            return 'Plugin `%s` requires dependency `%s`' % (self.issued_by, self.missing)

    def _set_message(self, message):
        self._message = message

    def has_message(self):
        return self._message is not None

    message = property(_get_message, _set_message)

    def __str__(self):
        return '<DependencyError(issued_by=%r,missing=%r,message=%r,silent=%r)>' % (
            self.issued_by,
            self.missing,
            self.message,
            self.silent,
        )


class RegisterException(Exception):
    def __init__(self, value):
        super(RegisterException, self).__init__()
        self.value = value

    def __str__(self):
        return repr(self.value)


@python_2_unicode_compatible
class PluginWarning(Warning):
    def __init__(self, value, logger=log, **kwargs):
        super(PluginWarning, self).__init__()
        self.value = value
        self.log = logger
        self.kwargs = kwargs

    def __str__(self):
        return self.value


@python_2_unicode_compatible
class PluginError(Exception):
    def __init__(self, value, logger=log, **kwargs):
        super(PluginError, self).__init__()
        # Value is expected to be a string
        if not isinstance(value, str):
            value = str(value)
        self.value = value
        self.log = logger
        self.kwargs = kwargs

    def __str__(self):
        return self.value


# TODO: move to utils or somewhere more appropriate
class internet(object):
    """@internet decorator for plugin phase methods.

    Catches all internet related exceptions and raises PluginError with relevant message.
    Task handles PluginErrors by aborting the task.
    """

    def __init__(self, logger=None):
        if logger:
            self.log = logger
        else:
            self.log = logging.getLogger('@internet')

    def __call__(self, func):
        def wrapped_func(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except RequestException as e:
                log.debug('decorator caught RequestException. handled traceback:', exc_info=True)
                raise PluginError('RequestException: %s' % e)
            except HTTPError as e:
                raise PluginError('HTTPError %s' % e.code, self.log)
            except URLError as e:
                log.debug('decorator caught urlerror. handled traceback:', exc_info=True)
                raise PluginError('URLError %s' % e.reason, self.log)
            except BadStatusLine:
                log.debug('decorator caught badstatusline. handled traceback:', exc_info=True)
                raise PluginError('Got BadStatusLine', self.log)
            except ValueError as e:
                log.debug('decorator caught ValueError. handled traceback:', exc_info=True)
                raise PluginError(e)
            except IOError as e:
                log.debug('decorator caught ioerror. handled traceback:', exc_info=True)
                if hasattr(e, 'reason'):
                    raise PluginError('Failed to reach server. Reason: %s' % e.reason, self.log)
                elif hasattr(e, 'code'):
                    raise PluginError(
                        'The server couldn\'t fulfill the request. Error code: %s' % e.code,
                        self.log,
                    )
                raise PluginError('IOError when connecting to server: %s' % e, self.log)

        return wrapped_func


def priority(value):
    """Priority decorator for phase methods"""

    def decorator(target):
        target.priority = value
        return target

    return decorator


# task phases, in order of their execution; note that this can be extended by
# registering new phases at runtime
task_phases = [
    'prepare',
    'start',
    'input',
    'metainfo',
    'filter',
    'download',
    'modify',
    'output',
    'learn',
    'exit',
]

# map phase names to method names
phase_methods = {
    # task
    'abort': 'on_task_abort'  # special; not a task phase that gets called normally
}
phase_methods.update((_phase, 'on_task_' + _phase) for _phase in task_phases)  # DRY

# Mapping of plugin name to PluginInfo instance (logical singletons)
plugins = {}

# Loading done?
plugins_loaded = False

_loaded_plugins = {}
_plugin_options = []
_new_phase_queue = {}


def register_task_phase(name, before=None, after=None):
    """
    Adds a new task phase to the available phases.

    :param suppress_abort: If True, errors during this phase will be suppressed, and not affect task result.
    """
    if before and after:
        raise RegisterException('You can only give either before or after for a phase.')
    if not before and not after:
        raise RegisterException('You must specify either a before or after phase.')
    if name in task_phases or name in _new_phase_queue:
        raise RegisterException('Phase %s already exists.' % name)

    def add_phase(phase_name, before, after):
        if before is not None and before not in task_phases:
            return False
        if after is not None and after not in task_phases:
            return False
        # add method name to phase -> method lookup table
        phase_methods[phase_name] = 'on_task_' + phase_name
        # place phase in phase list
        if before is None:
            task_phases.insert(task_phases.index(after) + 1, phase_name)
        if after is None:
            task_phases.insert(task_phases.index(before), phase_name)
        return True

    # if can't add yet (dependencies) queue addition
    if not add_phase(name, before, after):
        _new_phase_queue[name] = [before, after]

    for phase_name, args in list(_new_phase_queue.items()):
        if add_phase(phase_name, *args):
            del _new_phase_queue[phase_name]


@total_ordering
class PluginInfo(dict):
    """
    Allows accessing key/value pairs of this dictionary subclass via
    attributes. Also instantiates a plugin and initializes properties.
    """

    # Counts duplicate registrations
    dupe_counter = 0

    def __init__(
        self,
        plugin_class,
        name=None,
        interfaces=None,
        builtin=False,
        debug=False,
        api_ver=1,
        category=None,
    ):
        """
        Register a plugin.

        :param plugin_class: The plugin factory.
        :param string name: Name of the plugin (if not given, default to factory class name in underscore form).
        :param list interfaces: Interfaces this plugin implements.
        :param bool builtin: Auto-activated?
        :param bool debug: True if plugin is for debugging purposes.
        :param int api_ver: Signature of callback hooks (1=task; 2=task,config).
        :param string category: The type of plugin. Can be one of the task phases.
            Defaults to the package name containing the plugin.
        :param groups: DEPRECATED
        """
        dict.__init__(self)

        if interfaces is None:
            interfaces = ['task']
        if name is None:
            # Convention is to take camel-case class name and rewrite it to an underscore form,
            # e.g. 'PluginName' to 'plugin_name'
            name = re.sub(
                '[A-Z]+', lambda i: '_' + i.group(0).lower(), plugin_class.__name__
            ).lstrip('_')
        if category is None and plugin_class.__module__.startswith('flexget.plugins'):
            # By default look at the containing package of the plugin.
            category = plugin_class.__module__.split('.')[-2]

        # Check for unsupported api versions
        if api_ver < 2:
            raise PluginError('Api versions <2 are no longer supported. Plugin %s' % name)

        # Set basic info attributes
        self.api_ver = api_ver
        self.name = name
        self.interfaces = interfaces
        self.builtin = builtin
        self.debug = debug
        self.category = category
        self.phase_handlers = {}

        self.plugin_class = plugin_class
        self.instance = None

        if self.name in plugins:
            PluginInfo.dupe_counter += 1
            log.critical(
                'Error while registering plugin %s. '
                'A plugin with the same name is already registered',
                self.name,
            )
        else:
            plugins[self.name] = self

    def initialize(self):
        if self.instance is not None:
            # We already initialized
            return
        # Create plugin instance
        self.instance = self.plugin_class()
        self.instance.plugin_info = self  # give plugin easy access to its own info
        self.instance.log = logging.getLogger(
            getattr(self.instance, "LOGGER_NAME", None) or self.name
        )
        if hasattr(self.instance, 'schema'):
            self.schema = self.instance.schema
        elif hasattr(self.instance, 'validator'):
            self.schema = self.instance.validator().schema()
        else:
            # TODO: I think plugins without schemas should not be allowed in config, maybe rethink this
            self.schema = {}

        if self.schema is not None:
            location = '/schema/plugin/%s' % self.name
            self.schema['id'] = location
            config_schema.register_schema(location, self.schema)

        self.build_phase_handlers()

    def reset_phase_handlers(self):
        """Temporary utility method"""
        self.phase_handlers = {}
        self.build_phase_handlers()
        # TODO: should unregister events (from flexget.event)
        # this method is not used at the moment anywhere ...
        raise NotImplementedError

    def build_phase_handlers(self):
        """(Re)build phase_handlers in this plugin"""
        for phase, method_name in phase_methods.items():
            if phase in self.phase_handlers:
                continue
            if hasattr(self.instance, method_name):
                method = getattr(self.instance, method_name)
                if not callable(method):
                    continue
                # check for priority decorator
                if hasattr(method, 'priority'):
                    handler_prio = method.priority
                else:
                    handler_prio = PRIORITY_DEFAULT
                event = add_phase_handler(
                    'plugin.%s.%s' % (self.name, phase), method, handler_prio
                )
                # provides backwards compatibility
                event.plugin = self
                self.phase_handlers[phase] = event

    def __getattr__(self, attr):
        if attr in self:
            return self[attr]
        return dict.__getattribute__(self, attr)

    def __setattr__(self, attr, value):
        self[attr] = value

    def __str__(self):
        return '<PluginInfo(name=%s)>' % self.name

    def _is_valid_operand(self, other):
        return hasattr(other, 'name')

    def __eq__(self, other):
        return self.name == other.name

    def __lt__(self, other):
        return self.name < other.name

    __repr__ = __str__


register = PluginInfo


def _strip_trailing_sep(path):
    return path.rstrip("\\/")


def _get_standard_plugins_path():
    """
    :returns: List of directories where traditional plugins should be tried to load from.
    """
    # Get basic path from environment
    paths = []
    env_path = os.environ.get('FLEXGET_PLUGIN_PATH')
    if env_path:
        paths = env_path.split(os.pathsep)

    # Add flexget.plugins directory (core plugins)
    paths.append(os.path.abspath(os.path.dirname(plugins_pkg.__file__)))
    return paths


def _get_standard_components_path():
    """
    :returns: List of directories where component plugins should be tried to load from.
    """
    # Get basic path from environment
    paths = []
    env_path = os.environ.get('FLEXGET_COMPONENT_PATH')
    if env_path:
        paths = env_path.split(os.pathsep)

    # Add flexget.plugins directory (core plugins)
    paths.append(os.path.abspath(os.path.dirname(components_pkg.__file__)))
    return paths


def _check_phase_queue():
    if _new_phase_queue:
        for phase, args in _new_phase_queue.items():
            log.error(
                'Plugin %s requested new phase %s, but it could not be created at requested '
                'point (before, after). Plugin is not working properly.',
                args[0],
                phase,
            )


def _import_plugin(module_name, plugin_path):
    try:
        import_module(module_name)
    except DependencyError as e:
        if e.has_message():
            msg = e.message
        else:
            msg = 'Plugin `%s` requires plugin `%s` to load.' % (
                e.issued_by or module_name,
                e.missing or 'N/A',
            )
        if not e.silent:
            log.warning(msg)
        else:
            log.debug(msg)
    except ImportError:
        log.critical('Plugin `%s` failed to import dependencies', module_name, exc_info=True)
    except ValueError as e:
        # Debugging #2755
        log.error(
            'ValueError attempting to import `%s` (from %s): %s', module_name, plugin_path, e
        )
    except Exception:
        log.critical('Exception while loading plugin %s', module_name, exc_info=True)
        raise
    else:
        log.trace('Loaded module %s from %s', module_name, plugin_path)


def _load_plugins_from_dirs(dirs):
    """
    :param list dirs: Directories from where plugins are loaded from
    """

    log.debug('Trying to load plugins from: %s', dirs)
    dirs = [Path(d) for d in dirs if os.path.isdir(d)]
    # add all dirs to plugins_pkg load path so that imports work properly from any of the plugin dirs
    plugins_pkg.__path__ = list(map(_strip_trailing_sep, dirs))
    for plugins_dir in dirs:
        for plugin_path in plugins_dir.walkfiles('*.py'):
            if plugin_path.name == '__init__.py':
                continue
            # Split the relative path from the plugins dir to current file's parent dir to find subpackage names
            plugin_subpackages = [
                _f for _f in plugin_path.relpath(plugins_dir).parent.splitall() if _f
            ]
            module_name = '.'.join(
                [plugins_pkg.__name__] + plugin_subpackages + [plugin_path.stem]
            )
            _import_plugin(module_name, plugin_path)
    _check_phase_queue()


# TODO: this is now identical to _load_plugins_from_dirs, REMOVE
def _load_components_from_dirs(dirs):
    """
    :param list dirs: Directories where plugin components are loaded from
    """
    log.debug('Trying to load components from: %s', dirs)
    dirs = [Path(d) for d in dirs if os.path.isdir(d)]
    for component_dir in dirs:
        for component_path in component_dir.walkfiles('*.py'):
            if component_path.name == '__init__.py':
                continue
            # Split the relative path from the plugins dir to current file's parent dir to find subpackage names
            plugin_subpackages = [
                _f for _f in component_path.relpath(component_dir).parent.splitall() if _f
            ]
            package_name = '.'.join(
                [components_pkg.__name__] + plugin_subpackages + [component_path.stem]
            )
            _import_plugin(package_name, component_path)
    _check_phase_queue()


def _load_plugins_from_packages():
    """Load plugins installed via PIP"""
    for entrypoint in pkg_resources.iter_entry_points('FlexGet.plugins'):
        try:
            plugin_module = entrypoint.load()
        except DependencyError as e:
            if e.has_message():
                msg = e.message
            else:
                msg = (
                    'Plugin `%s` requires `%s` to load.',
                    e.issued_by or entrypoint.module_name,
                    e.missing or 'N/A',
                )
            if not e.silent:
                log.warning(msg)
            else:
                log.debug(msg)
        except ImportError:
            log.critical(
                'Plugin `%s` failed to import dependencies', entrypoint.module_name, exc_info=True
            )
        except Exception:
            log.critical(
                'Exception while loading plugin %s', entrypoint.module_name, exc_info=True
            )
            raise
        else:
            log.trace(
                'Loaded packaged module %s from %s', entrypoint.module_name, plugin_module.__file__
            )
    _check_phase_queue()


def load_plugins(extra_plugins=None, extra_components=None):
    """
    Load plugins from the standard plugin and component paths.

    :param list extra_plugins: Extra directories from where plugins are loaded.
    :param list extra_components: Extra directories from where components are loaded.
    """
    global plugins_loaded

    if extra_plugins is None:
        extra_plugins = []
    if extra_components is None:
        extra_components = []

    # Add flexget.plugins and flexget.components directories (core dist)
    extra_plugins.extend(_get_standard_plugins_path())
    extra_components.extend(_get_standard_components_path())

    start_time = time.time()
    # Import all the plugins
    _load_plugins_from_dirs(extra_plugins)
    _load_components_from_dirs(extra_components)
    _load_plugins_from_packages()
    # Register them
    fire_event('plugin.register')
    # Plugins should only be registered once, remove their handlers after
    remove_event_handlers('plugin.register')
    # After they have all been registered, instantiate them
    for plugin in list(plugins.values()):
        plugin.initialize()
    took = time.time() - start_time
    plugins_loaded = True
    log.debug(
        'Plugins took %.2f seconds to load. %s plugins in registry.', took, len(plugins.keys())
    )


def get_plugins(phase=None, interface=None, category=None, name=None, min_api=None):
    """
    Query other plugins characteristics.

    :param string phase: Require phase
    :param string interface: Plugin must implement this interface.
    :param string category: Type of plugin, phase names.
    :param string name: Name of the plugin.
    :param int min_api: Minimum api version.
    :return: List of PluginInfo instances.
    :rtype: list
    """

    def matches(plugin):
        if phase is not None and phase not in phase_methods:
            raise ValueError('Unknown phase %s' % phase)
        if phase and phase not in plugin.phase_handlers:
            return False
        if interface and interface not in plugin.interfaces:
            return False
        if category and not category == plugin.category:
            return False
        if name is not None and name != plugin.name:
            return False
        if min_api is not None and plugin.api_ver < min_api:
            return False
        return True

    return filter(matches, iter(plugins.values()))


def plugin_schemas(**kwargs):
    """Create a dict schema that matches plugins specified by `kwargs`"""
    return {
        'type': 'object',
        'properties': dict((p.name, {'$ref': p.schema['id']}) for p in get_plugins(**kwargs)),
        'additionalProperties': False,
        'error_additionalProperties': '{{message}} Only known plugin names are valid keys.',
        'patternProperties': {'^_': {'title': 'Disabled Plugin'}},
    }


config_schema.register_schema('/schema/plugins', plugin_schemas)


def get_phases_by_plugin(name):
    """Return all phases plugin :name: hooks"""
    return list(get_plugin_by_name(name).phase_handlers)


def get_plugin_by_name(name, issued_by='???'):
    """
    Get plugin by name, preferred way since this structure may be changed at some point.

    Getting plugin via `.get` function is recommended for normal use.

    This results much shorter and cleaner code::

        plugin.get_plugin_by_name('parsing').instance.parse_movie(data=entry['title'])

    Shortens into::

        plugin.get('parsing', self).parse_movie(data=entry['title'])

    This function is still useful if you need to access plugin information (PluginInfo).

    :returns PluginInfo instance
    """
    if name not in plugins:
        raise DependencyError(issued_by=issued_by, missing=name)
    return plugins[name]


def get(name, requested_by):
    """

    :param str name: Name of the requested plugin
    :param requested_by: Plugin class instance OR string value who is making the request.
    :return: Instance of Plugin class
    """
    if name not in plugins:
        if hasattr(requested_by, 'plugin_info'):
            who = requested_by.plugin_info.name
        else:
            who = requested_by
        raise DependencyError(issued_by=who, missing=name)

    instance = plugins[name].instance
    if instance is None:
        raise Exception('Plugin referred before system initialized?')
    return instance
