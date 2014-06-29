""" Plugin Loading & Management.
"""

from __future__ import unicode_literals, division, absolute_import
import sys
import os
import re
import logging
import time
import pkgutil
import warnings
from itertools import ifilter

from requests import RequestException

from flexget import config_schema
from flexget.event import add_event_handler as add_phase_handler, fire_event, remove_event_handlers
from flexget import plugins as plugins_pkg

log = logging.getLogger('plugin')

__all__ = ['PluginWarning', 'PluginError', 'register_plugin', 'register_parser_option', 'register_task_phase',
           'get_plugin_by_name', 'get_plugins_by_group', 'get_plugin_keywords', 'get_plugins_by_phase',
           'get_phases_by_plugin', 'internet', 'priority']


class DependencyError(Exception):
    """Plugin depends on other plugin, but it cannot be loaded.

    Args:
        issued_by: name of the plugin trying to do the import
        missing: name of the plugin or library that is missing
        message: user readable error message

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
        return '<DependencyError(issued_by=%r,missing=%r,message=%r,silent=%r)>' % \
            (self.issued_by, self.missing, self.message, self.silent)


class RegisterException(Exception):

    def __init__(self, value):
        super(RegisterException, self).__init__()
        self.value = value

    def __str__(self):
        return repr(self.value)


class PluginWarning(Warning):

    def __init__(self, value, logger=log, **kwargs):
        super(PluginWarning, self).__init__()
        self.value = value
        self.log = logger
        self.kwargs = kwargs

    def __str__(self):
        return unicode(self).encode('utf-8')

    def __unicode__(self):
        return self.value


class PluginError(Exception):

    def __init__(self, value, logger=log, **kwargs):
        super(PluginError, self).__init__()
        # Value is expected to be a string
        if not isinstance(value, basestring):
            value = unicode(value)
        self.value = value
        self.log = logger
        self.kwargs = kwargs

    def __str__(self):
        return unicode(self).encode('utf-8')

    def __unicode__(self):
        return unicode(self.value)


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
            from httplib import BadStatusLine
            import urllib2
            try:
                return func(*args, **kwargs)
            except RequestException as e:
                log.debug('decorator caught RequestException. handled traceback:', exc_info=True)
                raise PluginError('RequestException: %s' % e)
            except urllib2.HTTPError as e:
                raise PluginError('HTTPError %s' % e.code, self.log)
            except urllib2.URLError as e:
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
                    raise PluginError('The server couldn\'t fulfill the request. Error code: %s' % e.code, self.log)
                raise PluginError('IOError when connecting to server: %s' % e, self.log)
        return wrapped_func


def priority(value):
    """Priority decorator for phase methods"""

    def decorator(target):
        target.priority = value
        return target
    return decorator

DEFAULT_PRIORITY = 128

plugin_contexts = ['task', 'root']

# task phases, in order of their execution; note that this can be extended by
# registering new phases at runtime
task_phases = ['start', 'input', 'metainfo', 'filter', 'download', 'modify', 'output', 'learn', 'exit']

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
    """Adds a new task phase to the available phases."""
    if before and after:
        raise RegisterException('You can only give either before or after for a phase.')
    if not before and not after:
        raise RegisterException('You must specify either a before or after phase.')
    if name in task_phases or name in _new_phase_queue:
        raise RegisterException('Phase %s already exists.' % name)

    def add_phase(phase_name, before, after):
        if not before is None and not before in task_phases:
            return False
        if not after is None and not after in task_phases:
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

    for phase_name, args in _new_phase_queue.items():
        if add_phase(phase_name, *args):
            del _new_phase_queue[phase_name]


class PluginInfo(dict):
    """
    Allows accessing key/value pairs of this dictionary subclass via
    attributes. Also instantiates a plugin and initializes properties.
    """
    # Counts duplicate registrations
    dupe_counter = 0

    def __init__(self, plugin_class, name=None, groups=None, builtin=False, debug=False, api_ver=1,
                 contexts=None, category=None):
        """
        Register a plugin.

        :param plugin_class: The plugin factory.
        :param string name: Name of the plugin (if not given, default to factory class name in underscore form).
        :param list groups: Groups this plugin belongs to.
        :param bool builtin: Auto-activated?
        :param bool debug: True if plugin is for debugging purposes.
        :param int api_ver: Signature of callback hooks (1=task; 2=task,config).
        :param list contexts: List of where this plugin is configurable. Can be 'task', 'root', or None
        :param string category: The type of plugin. Can be one of the task phases.
            Defaults to the package name containing the plugin.
        """
        dict.__init__(self)

        if groups is None:
            groups = []
        if name is None:
            # Convention is to take camel-case class name and rewrite it to an underscore form,
            # e.g. 'PluginName' to 'plugin_name'
            name = re.sub('[A-Z]+', lambda i: '_' + i.group(0).lower(), plugin_class.__name__).lstrip('_')
        if contexts is None:
            contexts = ['task']
        elif isinstance(contexts, basestring):
            contexts = [contexts]
        if category is None and plugin_class.__module__.startswith('flexget.plugins'):
            # By default look at the containing package of the plugin.
            category = plugin_class.__module__.split('.')[-2]

        # Check for unsupported api versions
        if api_ver < 2:
            warnings.warn('Api versions <2 are no longer supported. Plugin %s' % name, DeprecationWarning, stacklevel=2)

        # Set basic info attributes
        self.api_ver = api_ver
        self.name = name
        self.groups = groups
        self.builtin = builtin
        self.debug = debug
        self.contexts = contexts
        self.category = category
        self.phase_handlers = {}

        self.plugin_class = plugin_class
        self.instance = None

        if self.name in plugins:
            PluginInfo.dupe_counter += 1
            log.critical('Error while registering plugin %s. A plugin with the same name is already registered' %
                         self.name)
        else:
            plugins[self.name] = self

    def initialize(self):
        if self.instance is not None:
            # We already initialized
            return
        # Create plugin instance
        self.instance = self.plugin_class()
        self.instance.plugin_info = self  # give plugin easy access to its own info
        self.instance.log = logging.getLogger(getattr(self.instance, "LOGGER_NAME", None) or self.name)
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
        for phase, method_name in phase_methods.iteritems():
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
                    handler_prio = DEFAULT_PRIORITY
                event = add_phase_handler('plugin.%s.%s' % (self.name, phase), method, handler_prio)
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

    __repr__ = __str__


register = PluginInfo


def _strip_trailing_sep(path):
    return path.rstrip("\\/")


def _get_standard_plugins_path():
    """
    :returns: List of directories where plugins should be tried to load from.
    """
    # Get basic path from environment
    env_path = os.environ.get('FLEXGET_PLUGIN_PATH')
    if env_path:
        # Get rid of trailing slashes, since Python can't handle them when
        # it tries to import modules.
        paths = map(_strip_trailing_sep, env_path.split(os.pathsep))
    else:
        # Use standard default
        paths = [os.path.join(os.path.expanduser('~'), '.flexget', 'plugins')]

    # Add flexget.plugins directory (core plugins)
    paths.append(os.path.abspath(os.path.dirname(plugins_pkg.__file__)))
    return paths


def _load_plugins_from_dirs(dirs):
    """
    :param list dirs: Directories from where plugins are loaded from
    """

    log.debug('Trying to load plugins from: %s' % dirs)
    # add all dirs to plugins_pkg load path so that plugins are loaded from flexget and from ~/.flexget/plugins/
    plugins_pkg.__path__ = map(_strip_trailing_sep, dirs)
    for importer, name, ispkg in pkgutil.walk_packages(dirs, plugins_pkg.__name__ + '.'):
        if ispkg:
            continue
        # Don't load any plugins again if they are already loaded
        # This can happen if one plugin imports from another plugin
        if name in sys.modules:
            continue
        loader = importer.find_module(name)
        # Don't load from pyc files
        if not loader.filename.endswith('.py'):
            continue
        try:
            loaded_module = loader.load_module(name)
        except DependencyError as e:
            if e.has_message():
                msg = e.message
            else:
                msg = 'Plugin `%s` requires `%s` to load.' % (e.issued_by or name, e.missing or 'N/A')
            if not e.silent:
                log.warning(msg)
            else:
                log.debug(msg)
        except ImportError as e:
            log.critical('Plugin `%s` failed to import dependencies' % name)
            log.exception(e)
        except Exception as e:
            log.critical('Exception while loading plugin %s' % name)
            log.exception(e)
            raise
        else:
            log.trace('Loaded module %s from %s' % (name, loaded_module.__file__))

    if _new_phase_queue:
        for phase, args in _new_phase_queue.iteritems():
            log.error('Plugin %s requested new phase %s, but it could not be created at requested '
                      'point (before, after). Plugin is not working properly.' % (args[0], phase))


def load_plugins():
    """Load plugins from the standard plugin paths."""
    global plugins_loaded

    start_time = time.time()
    # Import all the plugins
    _load_plugins_from_dirs(_get_standard_plugins_path())
    # Register them
    fire_event('plugin.register')
    # Plugins should only be registered once, remove their handlers after
    remove_event_handlers('plugin.register')
    # After they have all been registered, instantiate them
    for plugin in plugins.values():
        plugin.initialize()
    took = time.time() - start_time
    plugins_loaded = True
    log.debug('Plugins took %.2f seconds to load' % took)


def get_plugins(phase=None, group=None, context=None, category=None, min_api=None):
    """
    Query other plugins characteristics.

    :param string phase: Require phase
    :param string group: Plugin must belong to this group.
    :param string context: Where plugin is configured, eg. (root, task)
    :param string category: Type of plugin, phase names.
    :param int min_api: Minimum api version.
    :return: List of PluginInfo instances.
    :rtype: list
    """
    def matches(plugin):
        if phase is not None and phase not in phase_methods:
            raise ValueError('Unknown phase %s' % phase)
        if phase and not phase in plugin.phase_handlers:
            return False
        if group and not group in plugin.groups:
            return False
        if context and not context in plugin.contexts:
            return False
        if category and not category == plugin.category:
            return False
        if min_api is not None and plugin.api_ver < min_api:
            return False
        return True
    return ifilter(matches, plugins.itervalues())


def plugin_schemas(**kwargs):
    """Create a dict schema that matches plugins specified by `kwargs`"""
    return {'type': 'object',
            'properties': dict((p.name, {'$ref': p.schema['id']}) for p in get_plugins(**kwargs)),
            'additionalProperties': False,
            'error_additionalProperties': '{{message}} Only known plugin names are valid keys.',
            'patternProperties': {'^_': {'title': 'Disabled Plugin'}}}


config_schema.register_schema('/schema/plugins', plugin_schemas)


def get_plugins_by_phase(phase):
    """
    .. deprecated:: 1.0.3328
       Use :func:`get_plugins` instead

    Return an iterator over all plugins that hook :phase:
    """
    warnings.warn('Deprecated API', DeprecationWarning, stacklevel=2)
    if not phase in phase_methods:
        raise Exception('Unknown phase %s' % phase)
    return get_plugins(phase=phase)


def get_phases_by_plugin(name):
    """Return all phases plugin :name: hooks"""
    return list(get_plugin_by_name(name).phase_handlers)


def get_plugins_by_group(group):
    """
    .. deprecated:: 1.0.3328
       Use :func:`get_plugins` instead

    Return an iterator over all plugins with in specified group.
    """
    warnings.warn('Deprecated API', DeprecationWarning, stacklevel=2)
    return get_plugins(group=group)


def get_plugin_keywords():
    """Return iterator over all plugin keywords."""
    return plugins.iterkeys()


def get_plugin_by_name(name, issued_by='???'):
    """Get plugin by name, preferred way since this structure may be changed at some point."""
    if not name in plugins:
        raise DependencyError(issued_by=issued_by, missing=name, message='Unknown plugin %s' % name)
    return plugins[name]
