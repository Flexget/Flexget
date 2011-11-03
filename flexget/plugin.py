""" Plugin Loading & Management.
"""

from flexget import plugins as plugins_pkg
import sys
import os
import re
import logging
import time
from event import add_event_handler as add_phase_handler

log = logging.getLogger('plugin')

__all__ = ['PluginWarning', 'PluginError', 'register_plugin', 'register_parser_option', 'register_feed_phase',
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
        return self.value


class PluginError(Exception):

    def __init__(self, value, logger=log, **kwargs):
        super(PluginError, self).__init__()
        self.value = value
        self.log = logger
        self.kwargs = kwargs

    def __str__(self):
        return self.value


class internet(object):
    """@internet decorator for plugin phase methods.

    Catches all internet related exceptions and raises PluginError with relevant message.
    Feed handles PluginErrors by aborting the feed.
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
            except urllib2.HTTPError, e:
                raise PluginError('HTTPError %s' % e.code, self.log)
            except urllib2.URLError, e:
                log.debug('decorator caught urlerror')
                raise PluginError('URLError %s' % e.reason, self.log)
            except BadStatusLine:
                log.debug('decorator caught badstatusline')
                raise PluginError('Got BadStatusLine', self.log)
            except ValueError, e:
                log.debug('decorator caught ValueError')
                raise PluginError(e.message)
            except IOError, e:
                log.debug('decorator caught ioerror')
                if hasattr(e, 'reason'):
                    raise PluginError('Failed to reach server. Reason: %s' % e.reason, self.log)
                elif hasattr(e, 'code'):
                    raise PluginError('The server couldn\'t fulfill the request. Error code: %s' % e.code, self.log)
        return wrapped_func


def priority(value):
    """Priority decorator for phase methods"""

    def decorator(target):
        target.priority = value
        return target
    return decorator


def _strip_trailing_sep(path):
    return path.rstrip("\\/")

DEFAULT_PRIORITY = 128

# feed phases, in order of their execution; note that this can be extended by
# registering new phases at runtime
feed_phases = ['start', 'input', 'metainfo', 'filter', 'download', 'modify', 'output', 'exit']

# map phase names to method names
phase_methods = {
    # feed
    'abort': 'on_feed_abort', # special; not a feed phase that gets called normally

    # entry handling
    'accept': 'on_entry_accept',
    'reject': 'on_entry_reject',
    'fail': 'on_entry_fail',

    # lifecycle
    'process_start': 'on_process_start',
    'process_end': 'on_process_end',
}
phase_methods.update((_phase, 'on_feed_' + _phase) for _phase in feed_phases) # DRY

# Plugin package naming
PLUGIN_NAMESPACE = 'flexget.plugins'

# Mapping of plugin name to PluginInfo instance (logical singletons)
plugins = {}

# Loading done?
plugins_loaded = False

_parser = None
_loaded_plugins = {}
_plugin_options = []
_new_phase_queue = {}


def register_parser_option(*args, **kwargs):
    """Adds a parser option to the global parser."""
    _parser.add_option(*args, **kwargs)
    _plugin_options.append((args, kwargs))


def register_feed_phase(name, before=None, after=None):
    """Adds a new feed phase to the available phases."""
    if before and after:
        raise RegisterException('You can only give either before or after for a phase.')
    if not before and not after:
        raise RegisterException('You must specify either a before or after phase.')
    if name in feed_phases or name in _new_phase_queue:
        raise RegisterException('Phase %s already exists.' % name)

    def add_phase(phase_name, before, after):
        if not before is None and not before in feed_phases:
            return False
        if not after is None and not after in feed_phases:
            return False
        # add method name to phase -> method lookup table
        phase_methods[phase_name] = 'on_feed_' + phase_name
        # place phase in phase list
        if before is None:
            feed_phases.insert(feed_phases.index(after) + 1, phase_name)
        if after is None:
            feed_phases.insert(feed_phases.index(before), phase_name)

        # create possibly newly available phase handlers
        for loaded_plugin in plugins:
            plugins[loaded_plugin].build_phase_handlers()

        return True

    # if can't add yet (dependencies) queue addition
    if not add_phase(name, before, after):
        _new_phase_queue[name] = [before, after]

    for phase_name, args in _new_phase_queue.items():
        if add_phase(phase_name, *args):
            del _new_phase_queue[phase_name]


class Plugin(object):
    """
        Base class for auto-registering plugins.

        Note that inheriting form this class implies API version 2.
    """
    PLUGIN_INFO = dict(api_ver=2)
    LOGGER_NAME = None # use default name

    def __init__(self, plugin_info, *args, **kw):
        """Initialize basic plugin attributes."""
        self.plugin_info = plugin_info
        self.log = logging.getLogger(self.LOGGER_NAME or self.plugin_info.name)


class BuiltinPlugin(Plugin):
    """A builtin plugin."""
    PLUGIN_INFO = Plugin.PLUGIN_INFO.copy() # inherit base info
    PLUGIN_INFO.update(builtin=True)


class DebugPlugin(Plugin):
    """
        A plugin for debugging purposes.
    """
    # Note that debug plugins are never builtin, so we don't need a mixin
    PLUGIN_INFO = Plugin.PLUGIN_INFO.copy() # inherit base info
    PLUGIN_INFO.update(debug=True)


class PluginInfo(dict):
    """
        Allows accessing key/value pairs of this dictionary subclass via
        attributes.  Also instantiates a plugin and initializes properties.
    """
    # Counts duplicate registrations
    dupe_counter = 0

    @classmethod
    def name_from_class(cls, plugin_class):
        """Convention is to take camel-case class name and rewrite it to an underscore form, e.g. 'PluginName' to 'plugin_name'"""
        return re.sub('[A-Z]+', lambda i: '_' + i.group(0).lower(), plugin_class.__name__).lstrip('_')

    def __init__(self, plugin_class, name=None, groups=None, builtin=False, debug=False, api_ver=1):
        """ Register a plugin.

        :plugin_class: The plugin factory.
        :name: Name of the plugin (if not given, default to factory class name in underscore form).
        :groups: Groups this plugin belongs to.
        :builtin: Auto-activated?
        :debug: True if plugin is for debugging purposes.
        :api_ver: Signature of callback hooks (1=feed; 2=feed,config).
        """
        dict.__init__(self)

        if groups is None:
            groups = []
        if name is None:
            name = PluginInfo.name_from_class(plugin_class)

        # Set basic info attributes
        self.api_ver = api_ver
        self.name = name
        self.groups = groups
        self.builtin = builtin
        self.debug = debug
        self.phase_handlers = {}

        # Create plugin instance
        self.plugin_class = plugin_class
        if issubclass(self.plugin_class, Plugin):
            # Base class init needs plugin info immediately
            try:
                self.instance = self.plugin_class(self)
            except: # OK, gets re-raised
                log.error("Could not create plugin '%s' from class %s.%s" % (
                    self.name, self.plugin_class.__module__, self.plugin_class.__name__))
                raise
        else:
            # Manually registered
            self.instance = self.plugin_class()
            self.instance.plugin_info = self # give plugin easy access to its own info
            self.instance.log = logging.getLogger(getattr(self.instance, "LOGGER_NAME", None) or self.name)

        if self.name in plugins:
            PluginInfo.dupe_counter += 1
            log.critical('Error while registering plugin %s. %s' % \
                (self.name, ('A plugin with the name %s is already registered' % self.name)))
        else:
            self.build_phase_handlers()
            plugins[self.name] = self

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


register_plugin = PluginInfo


def register(plugin_class, groups=None, auto=False):
    """ Register plugin with attributes according to C{PLUGIN_INFO} class variable.
        Additional groups can be optionally provided.

        @return: Plugin info of registered plugin.
    """
    # Base classes outside of plugin modules are NEVER auto-registered; if you have ones
    # in a plugin module, use the "*PluginBase" naming convention
    if auto and plugin_class.__name__.endswith("PluginBase"):
        log.trace("NOT auto-registering plugin base class %s.%s" % (
            plugin_class.__module__, plugin_class.__name__))
        return

    info = plugin_class.PLUGIN_INFO
    name = PluginInfo.name_from_class(plugin_class)

    # If this very class was already registered, that's OK
    if name in plugins and plugin_class is plugins[name].plugin_class:
        if not auto:
            log.trace("Ignoring dupe registration of same class %s.%s" % (
                plugin_class.__module__, plugin_class.__name__))
        if groups:
            plugins[name].groups = list(set(groups) | set(plugins[name].groups))
        return plugins[name]
    else:
        if auto:
            log.trace("Auto-registering plugin %s" % name)
        return PluginInfo(plugin_class, name, list(set(info.get('groups', []) + (groups or []))),
            info.get('builtin', False), info.get('debug', False), info.get('api_ver', 1))


def get_standard_plugins_path():
    """Determine a plugin path suitable for general use."""
    # Get basic path from enironment
    env_path = os.environ.get('FLEXGET_PLUGIN_PATH')
    if env_path:
        # Get rid of trailing slashes, since Python can't handle them when
        # it tries to import modules.
        path = map(_strip_trailing_sep, env_path.split(os.pathsep))
    else:
        # Use standard default
        path = [os.path.join(os.path.expanduser('~'), '.flexget', 'plugins')]

    # Add flexget.plugins directory (core plugins)
    path.append(os.path.abspath(os.path.dirname(plugins_pkg.__file__)))

    # Leads to problems if flexget is imported via PYTHONPATH and another copy
    # is installed into site-packages, remove this altogether if nobody has any problems
    # (and those that have can use FLEXGET_PLUGIN_PATH explicitely)
    ## Search the arch independent path if we can determine that and
    ## the plugin is found nowhere else, and we're in default mode
    #if not env_path and sys.platform != 'win32':
    #    try:
    #        from distutils.sysconfig import get_python_lib
    #    except ImportError:
    #        # If distutuils is not available, we just won't add that path
    #        log.debug('FYI: Not adding archless plugin path due to distutils missing')
    #    else:
    #        archless_path = os.path.join(get_python_lib(), 'flexget', 'plugins')
    #        if archless_path not in path:
    #            log.debug("FYI: Adding archless plugin path '%s' from distutils" % archless_path)
    #            path.append(archless_path)

    return path


def load_plugins_from_dirs(dirs):
    """
    Args:
        dirs: list of directories from where plugins are loaded from
    """

    # add all dirs to plugins_pkg load path so that plugins are loaded from flexget and from ~/.flexget/plugins/
    plugins_pkg.__path__ = map(_strip_trailing_sep, dirs)

    # construct list of plugin_packages from all load path subdirectories
    plugin_packages = []
    for dir in dirs:
        if not os.path.exists(dir):
            continue
        plugin_packages.extend([n for n in os.listdir(dir) if os.path.isdir(os.path.join(dir, n))])

    # import plugin packages and manipulate their load paths
    for subpkg in plugin_packages[:]:
        # must be a proper python package with __init__.py
        if os.path.isdir(os.path.join(os.path.dirname(plugins_pkg.__file__), subpkg)) and \
           os.path.isfile(os.path.join(os.path.dirname(plugins_pkg.__file__), subpkg, '__init__.py')):

            # import sub-package and manipulate its search path so that all existing subdirs are in it
            getattr(__import__(PLUGIN_NAMESPACE, fromlist=[subpkg], level=0), subpkg).__path__ = [
                _strip_trailing_sep(os.path.join(package_base, subpkg))
                for package_base in dirs if os.path.isfile(os.path.join(package_base, subpkg, '__init__.py'))]
        else:
            log.debug('removing defunct plugin_package %s' % subpkg)
            plugin_packages.remove(subpkg)

    # actually load plugins from directories
    for dir in dirs:
        if not dir:
            continue
        if os.path.isdir(dir):
            log.debug('Looking for plugins in %s', dir)
            load_plugins_from_dir(dir)

            # Also look in sub-packages named like the feed phases, plus "generic"
            for subpkg in plugin_packages:
                subpath = os.path.join(dir, subpkg)
                if os.path.isdir(subpath):
                    # Only log existing subdirs
                    log.debug("Looking for sub-plugins in '%s'", subpath)
                    load_plugins_from_dir(dir, subpkg)
        else:
            log.debug('Ignoring non-existing plugin directory %s', dir)


def load_plugins_from_dir(basepath, subpkg=None):
    # Get the list of valid python suffixes for plugins
    # this includes .py, .pyc, and .pyo (depending on if we are running -O)
    # but it doesn't include compiled modules (.so, .dll, etc)
    #
    # This causes quite a bit problems when renaming plugins and is there really need to import .pyc / pyo?
    #
    # import imp
    # valid_suffixes = [suffix for suffix, mod_type, flags in imp.get_suffixes()
    #                         if flags in (imp.PY_SOURCE, imp.PY_COMPILED)]
    valid_suffixes = ['.py']
    namespace = PLUGIN_NAMESPACE + '.'
    dirpath = basepath
    if subpkg:
        namespace += subpkg + '.'
        dirpath = os.path.join(dirpath, subpkg)

    found_plugins = set()
    for filename in os.listdir(dirpath):
        path = os.path.join(dirpath, filename)
        if os.path.isfile(path):
            f_base, ext = os.path.splitext(filename)
            if ext in valid_suffixes:
                if f_base == '__init__':
                    continue # don't load __init__.py again
                if (namespace + f_base) in _loaded_plugins:
                    log.debug('Duplicate plugin module `%s` in `%s` ignored, `%s` already loaded!' % (
                        namespace + f_base, dirpath, _loaded_plugins[namespace + f_base]))
                else:
                    _loaded_plugins[namespace + f_base] = path
                    found_plugins.add(namespace + f_base)

    for modulename in found_plugins:
        try:
            __import__(modulename, level=0)
        except DependencyError, e:
            if e.has_message():
                msg = e.message
            else:
                msg = 'Plugin `%s` requires `%s` to load.' % (e.issued_by or modulename, e.missing or 'N/A')
            if not e.silent:
                log.warning(msg)
            else:
                log.debug(msg)
        except ImportError, e:
            log.critical('Plugin `%s` failed to import dependencies' % modulename)
            log.exception(e)
        except Exception, e:
            log.critical('Exception while loading plugin %s' % modulename)
            log.exception(e)
            raise
        else:
            log.trace('Loaded module %s from %s' % (modulename[len(PLUGIN_NAMESPACE) + 1:], dirpath))

            # Auto-register plugins that inherit from plugin base classes,
            # and weren't already registered manually
            for obj in vars(sys.modules[modulename]).values():
                try:
                    if not issubclass(obj, Plugin):
                        continue
                except TypeError:
                    continue # not a class
                else:
                    register(obj, auto=True)

    if _new_phase_queue:
        for phase, args in _new_phase_queue.iteritems():
            log.error('Plugin %s requested new phase %s, but it could not be created at requested '
                      'point (before, after). Plugin is not working properly.' % (args[0], phase))


def load_plugins(parser):
    """Load plugins from the standard plugin paths."""
    global plugins_loaded, _parser

    if plugins_loaded:
        if parser is not None:
            for args, kwargs in _plugin_options:
                parser.add_option(*args, **kwargs)
        return 0

    # suppress DeprecationWarning's
    import warnings
    warnings.simplefilter('ignore', DeprecationWarning)

    start_time = time.time()
    _parser = parser
    try:
        load_plugins_from_dirs(get_standard_plugins_path())
    finally:
        _parser = None
    took = time.time() - start_time
    plugins_loaded = True
    log.debug('Plugins took %.2f seconds to load' % took)


def get_plugins_by_phase(phase):
    """Return an iterator over all plugins that hook :phase:"""
    if not phase in phase_methods:
        raise Exception('Unknown phase %s' % phase)
    return (p for p in plugins.itervalues() if phase in p.phase_handlers)


def get_phases_by_plugin(name):
    """Return all phases plugin :name: hooks"""
    return list(get_plugin_by_name(name).phase_handlers)


def get_plugins_by_group(group):
    """Return an iterator over all plugins with in specified group."""
    return (p for p in plugins.itervalues() if group in p.get('groups'))


def get_plugin_keywords():
    """Return iterator over all plugin keywords."""
    return plugins.iterkeys()


def get_plugin_by_name(name, issued_by='???'):
    """Get plugin by name, preferred way since this structure may be changed at some point."""
    if not name in plugins:
        raise DependencyError(issued_by=issued_by, missing=name, message='Unknown plugin %s' % name)
    return plugins[name]


_excluded_recursively = []


def add_plugin_validators(validator, phase=None, group=None, excluded=None, api_ver=2):
    """
    :param validator: Instance of validator where other plugin validators are added into. (Eg. list or dict validator)
    :param phase: Name of phase which plugins are added.
    :param group: Name of group which plugins are added.
    :param excluded: List of plugin names to excluded.
    :param api_ver: Add only api_ver plugins (defaults to 2)

    :returns: dict validator wrapping the newly added validators
    """

    # NOTE:
    # I'm not entirely happy how this turned out, since plugins are usually configured in dict context
    # we must use dict wrapper in there (outer_validator), making this somewhat unsuitable for cases where
    # list should just accept list of plugins (see discover plugin)

    if excluded is None:
        excluded = []

    _excluded_recursively.extend(excluded)

    # Get a list of plugins
    valid_plugins = []
    if phase is not None:
        if not isinstance(phase, basestring):
            raise ValueError('Invalid phase `%s`' % repr(phase))
        valid_plugins.extend([plugin for plugin in get_plugins_by_phase(phase)
                              if plugin.api_ver == api_ver and plugin.name not in _excluded_recursively])

    if group is not None:
        if not isinstance(group, basestring):
            raise ValueError('Invalid group `%s`' % repr(group))
        valid_plugins.extend([plugin for plugin in get_plugins_by_group(group)
                              if plugin.name not in _excluded_recursively])

    # log.debug('valid_plugins: %s' % [plugin.name for plugin in valid_plugins])
    # log.debug('_excluded_recursively: %s' % _excluded_recursively)

    outer_validator = validator.accept('dict')
    # Build a dict validator that accepts the available input plugins and their settings
    for plugin in valid_plugins:
        # log.debug('adding: %s' % plugin.name)
        if hasattr(plugin.instance, 'validator'):
            outer_validator.accept(plugin.instance.validator, key=plugin.name)
        else:
            outer_validator.accept('any', key=plugin.name)

    for name in excluded:
        _excluded_recursively.remove(name)

    return validator
