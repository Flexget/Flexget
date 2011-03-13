""" Plugin Loading & Management.
"""

from flexget import plugins as _plugins_pkg
import sys
import os
import re
import imp
import glob
import logging
import time
from event import add_phase_handler
from uuid import NAMESPACE_DNS

log = logging.getLogger('plugin')

__all__ = ['PluginWarning', 'PluginError',
           'register_plugin', 'register_parser_option',
           'register_feed_phase',
           'get_plugin_by_name', 'get_plugins_by_group',
           'get_plugin_keywords', 'get_plugins_by_phase',
           'get_methods_by_phase', 'get_phases_by_plugin',
           'internet', 'priority']


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
PLUGIN_PACKAGES = feed_phases + ['generic', 'local']

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


def register_feed_phase(plugin_class, name, before=None, after=None):
    """Adds a new feed phase to the available phases."""
    if before and after:
        raise RegisterException('You can only give either before or after for a phase.')
    if not before and not after:
        raise RegisterException('You must specify either a before or after phase.')
    if name in feed_phases or name in _new_phase_queue:
        raise RegisterException('Phase %s already exists.' % name)

    def add_phase(phase_name, plugin_class, before, after):
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
    if not add_phase(name, plugin_class.__name__, before, after):
        _new_phase_queue[name] = [plugin_class.__name__, before, after]

    for phase_name, args in _new_phase_queue.items():
        if add_phase(phase_name, *args):
            del _new_phase_queue[phase_name]


class Plugin(object):
    """
        Base class for auto-registering plugins.

        Note that inheriting form this class implies API version 2.
    """
    PLUGIN_INFO = dict(api_ver=2)


class BuiltinPlugin(Plugin):
    """
        A builtin plugin.
    """
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

            @param plugin_class: The plugin factory.
            @param name: Name of the plugin (if not given, default to factory class name in underscore form).
            @param groups: Groups this plugin belongs to.
            @param builtin: Auto-activated?
            @param debug: True if plugin is for debugging purposes.
            @param api_ver: Signature of callback hooks (1=feed; 2=feed,config).
        """
        dict.__init__(self)

        if groups is None:
            groups = []
        if name is None:
            name = PluginInfo.name_from_class(plugin_class)

        self.api_ver = api_ver
        self.name = name
        self.plugin_class = plugin_class
        self.instance = self.plugin_class()
        self.groups = groups
        self.builtin = builtin
        self.debug = debug
        self.phase_handlers = {}

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
        for event, method_name in phase_methods.iteritems():
            if method_name in self.phase_handlers:
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
                event = add_phase_handler('plugin.%s.%s' % (self.name, event), method, handler_prio)
                # provides backwards compatibility
                event.plugin = self
                self.phase_handlers[method_name] = event

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


def register(plugin_class, groups=None):
    """ Register plugin with attributes according to C{PLUGIN_INFO} class variable.
        Additional groups can be optionally provided.
        
        @return: Plugin info of registered plugin. 
    """
    info = plugin_class.PLUGIN_INFO
    name = PluginInfo.name_from_class(plugin_class)

    # If this very class was already registered, that's OK
    if name in plugins and plugin_class is plugins[name].plugin_class:
        log.debugall("Ignoring dupe registration of same class %s.%s" % (
            plugin_class.__module__, plugin_class.__name__))
        if groups:
            plugins[name].groups = list(set(groups) | set(plugins[name].groups))
        return plugins[name]
    else:
        return PluginInfo(plugin_class, name, list(set(info.get('groups', []) + (groups or []))),
            info.get('builtin', False), info.get('debug', False), info.get('api_ver', 1))
    

def get_standard_plugins_path():
    """Determine a plugin path suitable for general use."""
    path = os.environ.get('FLEXGET_PLUGIN_PATH',
                          os.path.join(os.path.expanduser('~'), '.flexget', 'plugins')).split(os.pathsep)
    # Get rid of trailing slashes, since Python can't handle them when
    # it tries to import modules.
    path = map(_strip_trailing_sep, path)
    path.append(os.path.abspath(os.path.dirname(_plugins_pkg.__file__)))
    # search the arch independent path if we can determine that and
    # the plugin is found nowhere else
    if sys.platform != 'win32':
        try:
            from distutils.sysconfig import get_python_lib
        except ImportError:
            # If distutuils is not available, we just won't add that path
            pass
        else:
            archless_path = os.path.join(get_python_lib(), 'flexget', 'plugins')
            if archless_path not in path:
                path.append(archless_path)
    return path


def load_plugins_from_dirs(dirs):
    _plugins_pkg.__path__ = map(_strip_trailing_sep, dirs)

    # Import existing feed namespaces
    for subpkg in PLUGIN_PACKAGES[:]:
        if os.path.isdir(os.path.join(os.path.dirname(_plugins_pkg.__file__), subpkg)):
            # Import sub-package and manipulate its search path so that all existing subdirs
            # in our plugin path are bound to it
            getattr(__import__(PLUGIN_NAMESPACE, fromlist=[subpkg], level=0), subpkg).__path__ = [
                _strip_trailing_sep(os.path.join(i, subpkg))
                for i in dirs
                if os.path.isfile(os.path.join(i, subpkg, '__init__.py'))]
        else:
            PLUGIN_PACKAGES.remove(subpkg)

    for dirpath in dirs:
        if not dirpath:
            continue
        log.debug('Looking for plugins in %s', dirpath)
        if os.path.isdir(dirpath):
            load_plugins_from_dir(dirpath)

            # Also look in subpackages named like the feed phases, plus "generic"
            for subpkg in PLUGIN_PACKAGES:
                subpath = os.path.join(dirpath, subpkg)
                if os.path.isdir(subpath):
                    # Only log existing subdirs
                    log.debug("Looking for sub-plugins in '%s'", subpath)
                    load_plugins_from_dir(dirpath, subpkg)


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
            # TODO: logging does not seem to work from here
            import traceback
            traceback.print_exc(file=sys.stdout)
        except Exception, e:
            log.critical('Exception while loading plugin %s' % modulename)
            log.exception(e)
            raise
        else:
            log.debugall('Loaded module %s from %s' % (modulename[len(PLUGIN_NAMESPACE) + 1:], dirpath))

            # Auto-register plugins that inherit from plugin base classes,
            # and weren't already registered manually
            for obj in vars(sys.modules[modulename]).values():
                try:
                    if not issubclass(obj, Plugin):
                        continue
                except TypeError:
                    continue # not a class
                else:
                    register(obj)

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
    return took


def get_plugins_by_phase(phase):
    """Return list of all plugins that hook :phase:"""
    result = []
    if not phase in phase_methods:
        raise Exception('Unknown phase %s' % phase)
    method_name = phase_methods[phase]
    for info in plugins.itervalues():
        instance = info.instance
        if not hasattr(instance, method_name):
            continue
        if callable(getattr(instance, method_name)):
            result.append(info)
    return result


def get_methods_by_phase(phase):
    """Return plugin methods that hook :phase: in order of priority (highest first)."""
    result = []
    if not phase in phase_methods:
        raise Exception('Unknown phase %s' % phase)
    method_name = phase_methods[phase]
    for info in plugins.itervalues():
        method = info.phase_handlers.get(method_name, None)
        if method:
            result.append(method)
    result.sort(reverse=True)
    return result


def get_phases_by_plugin(name):
    """Return all phases plugin :name: hooks"""
    plugin = get_plugin_by_name(name)
    phases = []
    for phase_name, method_name in phase_methods.iteritems():
        if hasattr(plugin.instance, method_name):
            phases.append(phase_name)
    return phases


def get_plugins_by_group(group):
    """Return all plugins with in specified group."""
    res = []
    for info in plugins.itervalues():
        if group in info.get('groups'):
            res.append(info)
    return res


def get_plugin_keywords():
    """Return all registered keywords in a list"""
    keywords = []
    for name in plugins.iterkeys():
        keywords.append(name)
    return keywords


def get_plugin_by_name(name, issued_by='???'):
    """Get plugin by name, preferred way since this structure may be changed at some point."""
    if not name in plugins:
        raise DependencyError(issued_by=issued_by, missing=name, message='Unknown plugin %s' % name)
    return plugins[name]
