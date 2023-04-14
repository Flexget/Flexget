import os
import re
import time
from functools import total_ordering
from http.client import BadStatusLine
from importlib import import_module
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Union
from urllib.error import HTTPError, URLError

import loguru
import pkg_resources
from requests import RequestException

from flexget import components as components_pkg
from flexget import config_schema
from flexget import plugins as plugins_pkg
from flexget.event import Event, event, fire_event, remove_event_handlers
from flexget.event import add_event_handler as add_phase_handler

logger = loguru.logger.bind(name='plugin')

PRIORITY_DEFAULT = 128
PRIORITY_LAST = -255
PRIORITY_FIRST = 255


class DependencyError(Exception):
    """Plugin depends on other plugin, but it cannot be loaded.

    Args:
        issued_by: name of the plugin trying to do the import
        missing: name of the plugin or library that is missing
        message: customized user readable error message

    All args are optional.
    """

    def __init__(
        self,
        issued_by: Optional[str] = None,
        missing: Optional[str] = None,
        message: Optional[str] = None,
        silent: bool = False,
    ):
        super().__init__()
        self.issued_by = issued_by
        self.missing = missing
        self._message = message
        self.silent = silent

    def _get_message(self) -> str:
        if self._message:
            return self._message
        return f'Plugin `{self.issued_by}` requires dependency `{self.missing}`'

    def _set_message(self, message: str) -> None:
        self._message = message

    def has_message(self) -> bool:
        return self._message is not None

    message = property(_get_message, _set_message)

    def __str__(self) -> str:
        return '<DependencyError(issued_by={!r},missing={!r},message={!r},silent={!r})>'.format(
            self.issued_by,
            self.missing,
            self.message,
            self.silent,
        )


class RegisterException(Exception):
    def __init__(self, value):
        super().__init__()
        self.value = value

    def __str__(self):
        return repr(self.value)


class PluginWarning(Warning):
    def __init__(self, value, logger: 'loguru.Logger' = logger, **kwargs):
        super().__init__()
        self.value = value
        self.logger = logger
        self.kwargs = kwargs

    def __str__(self):
        return self.value


class PluginError(Exception):
    def __init__(self, value, logger: 'loguru.Logger' = logger, **kwargs):
        super().__init__()
        # Value is expected to be a string
        if not isinstance(value, str):
            value = str(value)
        self.value = value
        self.logger = logger
        self.kwargs = kwargs

    def __str__(self):
        return self.value


# TODO: move to utils or somewhere more appropriate
class internet:
    """@internet decorator for plugin phase methods.

    Catches all internet related exceptions and raises PluginError with relevant message.
    Task handles PluginErrors by aborting the task.
    """

    def __init__(self, logger_: 'loguru.Logger' = logger):
        if logger_:
            self.logger = logger_
        else:
            self.logger = logger.bind(name='@internet')

    def __call__(self, func: Callable) -> Callable:
        def wrapped_func(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except RequestException as e:
                logger.opt(exception=True).debug(
                    'decorator caught RequestException. handled traceback:'
                )
                raise PluginError(f'RequestException: {e}')
            except HTTPError as e:
                raise PluginError(f'HTTPError {e.code}', self.logger)
            except URLError as e:
                logger.opt(exception=True).debug('decorator caught urlerror. handled traceback:')
                raise PluginError(f'URLError {e.reason}', self.logger)
            except BadStatusLine:
                logger.opt(exception=True).debug(
                    'decorator caught badstatusline. handled traceback:'
                )
                raise PluginError('Got BadStatusLine', self.logger)
            except ValueError as e:
                logger.opt(exception=True).debug('decorator caught ValueError. handled traceback:')
                raise PluginError(e)
            except OSError as e:
                logger.opt(exception=True).debug('decorator caught OSError. handled traceback:')
                if hasattr(e, 'reason'):
                    raise PluginError(f'Failed to reach server. Reason: {e.reason}', self.logger)
                if hasattr(e, 'code'):
                    raise PluginError(
                        f"The server couldn't fulfill the request. Error code: {e.code}",
                        self.logger,
                    )
                raise PluginError(f'OSError when connecting to server: {e}', self.logger)

        return wrapped_func


def priority(value: int) -> Callable[[Callable], Callable]:
    """Priority decorator for phase methods"""

    def decorator(target: Callable) -> Callable:
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
plugins: Dict[str, 'PluginInfo'] = {}

# Loading done?
plugins_loaded = False

_loaded_plugins = {}
_plugin_options = []
_new_phase_queue: Dict[str, List[Optional[str]]] = {}


def register_task_phase(name: str, before: str = None, after: str = None):
    """Adds a new task phase to the available phases."""
    if before and after:
        raise RegisterException('You can only give either before or after for a phase.')
    if not before and not after:
        raise RegisterException('You must specify either a before or after phase.')
    if name in task_phases or name in _new_phase_queue:
        raise RegisterException(f'Phase {name} already exists.')

    def add_phase(phase_name: str, before: Optional[str], after: Optional[str]):
        if before is not None and before not in task_phases:
            return False
        if after is not None and after not in task_phases:
            return False
        # add method name to phase -> method lookup table
        phase_methods[phase_name] = 'on_task_' + phase_name
        # place phase in phase list
        if before is None and after is not None:
            task_phases.insert(task_phases.index(after) + 1, phase_name)
        if after is None and before is not None:
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
        plugin_class: type,
        name: Optional[str] = None,
        interfaces: Optional[List[str]] = None,
        builtin: bool = False,
        debug: bool = False,
        api_ver: int = 1,
        category: Optional[str] = None,
    ) -> None:
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
        self.phase_handlers: Dict[str, Event] = {}
        self.schema: config_schema.JsonSchema = {}
        self.schema_id: Optional[str] = None

        self.plugin_class: type = plugin_class
        self.instance: object = None

        if self.name in plugins:
            PluginInfo.dupe_counter += 1
            logger.critical(
                'Error while registering plugin {}. A plugin with the same name is already registered',
                self.name,
            )
        else:
            plugins[self.name] = self

    def initialize(self) -> None:
        if self.instance is not None:
            # We already initialized
            return
        # Create plugin instance
        self.instance = self.plugin_class()
        self.instance.plugin_info = self  # give plugin easy access to its own info
        self.instance.logger = logger.bind(
            name=getattr(self.instance, "LOGGER_NAME", None) or self.name
        )
        if hasattr(self.instance, 'schema'):
            self.schema = self.instance.schema
        elif hasattr(self.instance, 'validator'):
            self.schema = self.instance.validator().schema()
        else:
            # TODO: I think plugins without schemas should not be allowed in config, maybe rethink this
            self.schema = {}

        if self.schema is not None:
            self.schema_id = f'/schema/plugin/{self.name}'
            config_schema.register_schema(self.schema_id, self.schema)

        self.build_phase_handlers()

    def build_phase_handlers(self) -> None:
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
                event = add_phase_handler(f'plugin.{self.name}.{phase}', method, handler_prio)
                # provides backwards compatibility
                event.plugin = self
                self.phase_handlers[phase] = event

    def __getattr__(self, attr: str):
        if attr in self:
            return self[attr]
        return dict.__getattribute__(self, attr)

    def __setattr__(self, attr: str, value):
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


def _get_standard_plugins_path() -> List[str]:
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


def _get_standard_components_path() -> List[str]:
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


def _check_phase_queue() -> None:
    if _new_phase_queue:
        for phase, args in _new_phase_queue.items():
            logger.error(
                'Plugin {} requested new phase {}, but it could not be created at requested point (before, after). '
                'Plugin is not working properly.',
                args[0],
                phase,
            )


def _import_plugin(module_name: str, plugin_path: Union[str, Path]) -> None:
    try:
        import_module(module_name)
    except DependencyError as e:
        if e.has_message():
            msg = e.message
        else:
            msg = 'Plugin `{}` requires plugin `{}` to load.'.format(
                e.issued_by or module_name,
                e.missing or 'N/A',
            )
        if not e.silent:
            logger.warning(msg)
        else:
            logger.debug(msg)
    except ImportError:
        logger.opt(exception=True).critical(
            'Plugin `{}` failed to import dependencies', module_name
        )
    except ValueError as e:
        # Debugging #2755
        logger.error(
            'ValueError attempting to import `{}` (from {}): {}', module_name, plugin_path, e
        )
    except Exception:
        logger.opt(exception=True).critical('Exception while loading plugin {}', module_name)
        raise
    else:
        logger.trace('Loaded module {} from {}', module_name, plugin_path)


def _load_plugins_from_dirs(dirs: List[str]) -> None:
    """
    :param list dirs: Directories from where plugins are loaded from
    """

    logger.debug(f'Trying to load plugins from: {dirs}')
    dir_paths = [Path(d) for d in dirs if os.path.isdir(d)]
    # add all dirs to plugins_pkg load path so that imports work properly from any of the plugin dirs
    plugins_pkg.__path__ = [str(d) for d in dir_paths]
    for plugins_dir in dir_paths:
        for plugin_path in plugins_dir.glob('**/*.py'):
            if plugin_path.name == '__init__.py':
                continue
            # Split the relative path from the plugins dir to current file's parent dir to find subpackage names
            plugin_subpackages = [
                _f for _f in plugin_path.relative_to(plugins_dir).parent.parts if _f
            ]
            module_name = '.'.join(
                [plugins_pkg.__name__, *plugin_subpackages] + [plugin_path.stem]
            )
            _import_plugin(module_name, plugin_path)
    _check_phase_queue()


# TODO: this is now identical to _load_plugins_from_dirs, REMOVE
def _load_components_from_dirs(dirs: List[str]) -> None:
    """
    :param list dirs: Directories where plugin components are loaded from
    """
    logger.debug('Trying to load components from: {}', dirs)
    dir_paths = [Path(d) for d in dirs if os.path.isdir(d)]
    for component_dir in dir_paths:
        for component_path in component_dir.glob('**/*.py'):
            if component_path.name == '__init__.py':
                continue
            # Split the relative path from the plugins dir to current file's parent dir to find subpackage names
            plugin_subpackages = [
                _f for _f in component_path.relative_to(component_dir).parent.parts if _f
            ]
            package_name = '.'.join(
                [components_pkg.__name__, *plugin_subpackages] + [component_path.stem]
            )
            _import_plugin(package_name, component_path)
    _check_phase_queue()


def _load_plugins_from_packages() -> None:
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
                logger.warning(msg)
            else:
                logger.debug(msg)
        except ImportError:
            logger.opt(exception=True).critical(
                'Plugin `{}` failed to import dependencies', entrypoint.module_name
            )
        except Exception:
            logger.opt(exception=True).critical(
                'Exception while loading plugin {}', entrypoint.module_name
            )
            raise
        else:
            logger.trace(
                'Loaded packaged module {} from {}', entrypoint.module_name, plugin_module.__file__
            )
    _check_phase_queue()


def load_plugins(
    extra_plugins: Optional[List[str]] = None, extra_components: Optional[List[str]] = None
) -> None:
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
    logger.debug(
        'Plugins took {:.2f} seconds to load. {} plugins in registry.', took, len(plugins.keys())
    )


def get_plugins(
    phase: Optional[str] = None,
    interface: Optional[str] = None,
    category: Optional[str] = None,
    name: Optional[str] = None,
    min_api: Optional[int] = None,
) -> Iterable[PluginInfo]:
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


def plugin_schemas(**kwargs) -> 'config_schema.JsonSchema':
    """Create a dict schema that matches plugins specified by `kwargs`"""
    return {
        'type': 'object',
        'properties': {p.name: {'$ref': p.schema_id} for p in get_plugins(**kwargs)},
        'additionalProperties': False,
        'error_additionalProperties': '{{message}} Only known plugin names are valid keys.',
        'patternProperties': {'^_': {'title': 'Disabled Plugin'}},
    }


@event('config.register')
def register_schema():
    config_schema.register_schema('/schema/plugins', plugin_schemas)


def get_phases_by_plugin(name: str) -> List[str]:
    """Return all phases plugin :name: hooks"""
    return list(get_plugin_by_name(name).phase_handlers)


def get_plugin_by_name(name: str, issued_by: str = '???') -> PluginInfo:
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


def get(name: str, requested_by: Union[str, object]) -> object:
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
