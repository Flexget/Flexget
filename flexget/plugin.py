from flexget import plugins as _plugins_mod
import os
import sys
import logging
import time

log = logging.getLogger('plugin')

__all__ = ['PluginWarning', 'PluginError',
           'PluginDependencyError', 'register_plugin',
           'register_parser_option', 'register_feed_event',
           'get_plugin_by_name', 'get_plugins_by_group',
           'get_plugin_keywords', 'get_plugins_by_event',
           'get_methods_by_event', 'get_events_by_plugin',
           'internet']


class PluginDependencyError(Exception):
    """A plugin has requested another plugin by name, but this plugin does not exists"""

    def __init__(self, value, plugin):
        self.value = value
        self.plugin = plugin

    def __str__(self):
        return '%s plugin: %s' % (repr(self.value), repr(self.plugin))


class RegisterException(Exception):

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class PluginWarning(Warning):

    def __init__(self, value, logger=log, **kwargs):
        self.value = value
        self.log = logger
        self.kwargs = kwargs

    def __str__(self):
        return self.value


class PluginError(Exception):

    def __init__(self, value, logger=log, **kwargs):
        self.value = value
        self.log = logger
        self.kwargs = kwargs

    def __str__(self):
        return self.value


class internet(object):
    """
        @internet decorator for plugin event methods.
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
            except IOError, e:
                log.debug('decorator caught ioerror')
                if hasattr(e, 'reason'):
                    raise PluginError('Failed to reach server. Reason: %s' % e.reason, self.log)
                elif hasattr(e, 'code'):
                    raise PluginError('The server couldn\'t fulfill the request. Error code: %s' % e.code, self.log)
        return wrapped_func


def _strip_trailing_sep(path):
    return path.rstrip("\\/")

DEFAULT_PRIORITY = 128

FEED_EVENTS = ['start', 'input', 'metainfo', 'filter', 'download', 'modify', 'output', 'exit']

# map event names to method names
EVENT_METHODS = {
    'start': 'on_feed_start',
    'input': 'on_feed_input',
    'metainfo': 'on_feed_metainfo',
    'filter': 'on_feed_filter',
    'download': 'on_feed_download',
    'modify': 'on_feed_modify',
    'output': 'on_feed_output',
    'exit': 'on_feed_exit',
    'abort': 'on_feed_abort',
    'process_start': 'on_process_start',
    'process_end': 'on_process_end'}
    
PREFIXES = FEED_EVENTS + ['module', 'plugin', 'source']

plugins = {}
plugins_loaded = False

_parser = None
_plugin_options = []
_new_event_queue = {}


def register_plugin(plugin_class, name, groups=[], builtin=False, debug=False, priorities={}):
    """Registers a plugin."""
    global plugins
    if name in plugins:
        log.critical('Error while registering plugin %s. %s' % \
            (name, ('A plugin with the name %s is already registered' % name)))
        return
    plugins[name] = PluginInfo(name, plugin_class, groups, builtin, debug, priorities)


def register_parser_option(*args, **kwargs):
    """Adds a parser option to the global parser."""
    global _parser, _plugin_options
    _parser.add_option(*args, **kwargs)
    _plugin_options.append((args, kwargs))


def register_feed_event(plugin_class, name, before=None, after=None):
    """Adds a new feed event to the available events."""
    global _new_event_queue, plugins

    if before and after:
        raise RegisterException('You can only give either before or after for a event.')
    if not before and not after:
        raise RegisterException('You must specify either a before or after event.')
    if name in FEED_EVENTS or name in _new_event_queue:
        raise RegisterException('Event %s already exists.' % name)

    def add_event(event_name, plugin_class, before, after):
        if not before is None and not before in FEED_EVENTS:
            return False
        if not after is None and not after in FEED_EVENTS:
            return False
        # add method name to event -> method lookup table
        EVENT_METHODS[event_name] = 'on_feed_' + event_name
        # queue plugin loading for this type
        PREFIXES.append(name)
        # place event in event list
        if before is None:
            FEED_EVENTS.insert(FEED_EVENTS.index(after) + 1, event_name)
        if after is None:
            FEED_EVENTS.insert(FEED_EVENTS.index(before), event_name)

        # update PluginInfo events flag
        for loaded_plugin in plugins:
            if plugins[loaded_plugin].events:
                continue
            if hasattr(plugins[loaded_plugin].instance, 'on_feed_' + name):
                if callable(getattr(plugins[loaded_plugin].instance, 'on_feed_' + name)):
                    plugins[loaded_plugin].events = True
                    continue
        return True

    # if can't add yet (dependencies) queue addition
    if not add_event(name, plugin_class.__name__, before, after):
        _new_event_queue[name] = [plugin_class.__name__, before, after]

    for event_name, args in _new_event_queue.items():
        if add_event(event_name, *args):
            del _new_event_queue[event_name]


class PluginInfo(dict):
    """
        Allows accessing key/value pairs of this dictionary subclass via
        attributes.  Also instantiates a plugin and initializes properties.
    """

    def __init__(self, name, item_class, groups=[], builtin=False, debug=False, priorities={}):
        dict.__init__(self)

        self.name = name
        self.item_class = item_class

        try:
            instance = item_class()
        except Exception:
            raise

        self.instance = instance
        self.groups = groups
        self.builtin = builtin
        self.debug = debug

        self.events = False
        for method_name in EVENT_METHODS.itervalues():
            if hasattr(instance, method_name):
                if callable(getattr(instance, method_name)):
                    self.events = True
                    break

        self.priorities = priorities

    def __getattr__(self, attr):
        if attr in self:
            return self[attr]
        return dict.__getattribute__(self, attr)

    def __setattr__(self, attr, value):
        self[attr] = value

    def __str__(self):
        return '<PluginInfo(name=%s)>' % self.name

    __repr__ = __str__


class PluginMethod(object):
    """
        Proxies an event for a plugin to be used as a callable object
        while also allowing accessing the plugin's attributes directly.
    """

    def __init__(self, plugin, method_name, event_name):
        self.plugin = plugin
        self.method_name = method_name
        self.event_name = event_name
        self.priority = plugin.priorities.get(event_name, DEFAULT_PRIORITY)

    def __getattr__(self, attr):
        if attr in self.plugin:
            return self.plugin[attr]
        return object.__getattribute__(self, attr)

    def __getitem__(self, key):
        return self.plugin[key]

    def __call__(self, *args, **kwargs):
        #print self
        #print "args:%s" % args
        #print "kwargs:%s" % kwargs
        return getattr(self.plugin.instance, self.method_name)(*args, **kwargs)

    def __str__(self):
        return '<PluginMethod(name=%s,method=%s,priority=%s)>' % (self.plugin['name'], self.method_name, self.priority)

    __repr__ = __str__


def get_standard_plugins_path():
    """Determine a plugin path suitable for general use."""
    path = os.environ.get('FLEXGET_PLUGIN_PATH',
                          os.path.join(os.path.expanduser('~'), '.flexget', 'plugins')).split(os.pathsep)
    # Get rid of trailing slashes, since Python can't handle them when
    # it tries to import modules.
    path = map(_strip_trailing_sep, path)
    path.append(os.path.abspath(os.path.dirname(_plugins_mod.__file__)))
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
    _plugins_mod.__path__ = map(_strip_trailing_sep, dirs)
    for d in dirs:
        if not d:
            continue
        log.debug('looking for plugins in %s', d)
        if os.path.isdir(d):
            load_plugins_from_dir(d)


def load_plugins_from_dir(d):
    # Get the list of valid python suffixes for plugins
    # this includes .py, .pyc, and .pyo (depending on if we are running -O)
    # but it doesn't include compiled modules (.so, .dll, etc)
    global _new_event_queue
    import imp
    valid_suffixes = [suffix for suffix, mod_type, flags in imp.get_suffixes()
                              if flags in (imp.PY_SOURCE, imp.PY_COMPILED)]
    plugin_names = set()
    for f in os.listdir(d):
        path = os.path.join(d, f)
        if os.path.isfile(path):
            f_base, ext = os.path.splitext(f)
            #path_parts = f_base.split('_')
            if ext in valid_suffixes:
                if f_base == '__init__':
                    continue # don't load __init__.py again
                elif getattr(_plugins_mod, f_base, None):
                    log.warning('Plugin named %s already loaded' % f_base)
                plugin_names.add(f_base)

    for name in plugin_names:
        try:
            exec "import flexget.plugins.%s" % name in {}
        except Exception, e:
            log.critical('Exception while loading plugin %s' % name)
            log.exception(e)
            raise

    if _new_event_queue:
        for event, args in _new_event_queue.iteritems():
            log.error('Plugin %s requested new event %s, but it could not be created at requested \
            point (before, after). Plugin is not working properly.' % (args[0], event))


def load_plugins(parser):
    """Load plugins from the standard plugin paths."""
    global plugins_loaded, _parser, _plugin_options
    if plugins_loaded:
        if parser is not None:
            for args, kwargs in _plugin_options:
                parser.add_option(*args, **kwargs)
        return 0

    # suppress DeprecationWarning's
    import warnings
    warnings.simplefilter('ignore', DeprecationWarning)

    start_time = time.clock()
    _parser = parser
    load_plugins_from_dirs(get_standard_plugins_path())
    _parser = None
    took = time.clock() - start_time
    plugins_loaded = True
    return took


def get_plugins_by_event(event):
    """Return all plugins that hook event in order of priority."""
    result = []
    if not event in EVENT_METHODS:
        raise Exception('Unknown event %s' % event)
    method_name = EVENT_METHODS[event]
    for info in plugins.itervalues():
        instance = info.instance
        if not hasattr(instance, method_name):
            continue
        if callable(getattr(instance, method_name)):
            result.append(info)
    # sort plugins into proper order
    result.sort(lambda x, y: cmp(x.get('priorities', {}).get(event, DEFAULT_PRIORITY), \
                                 y.get('priorities', {}).get(event, DEFAULT_PRIORITY)), reverse=True)
    return result


def get_methods_by_event(event):
    """Return plugin methods that hook event in order of priority."""
    result = []
    if not event in EVENT_METHODS:
        raise Exception('Unknown event %s' % event)
    method = EVENT_METHODS[event]
    for info in plugins.itervalues():
        instance = info.instance
        if not hasattr(instance, method):
            continue
        if callable(getattr(instance, method)):
            result.append(info)
    # sort plugins into proper order
    result.sort(lambda x, y: cmp(x.get('priorities', {}).get(event, DEFAULT_PRIORITY), \
                                 y.get('priorities', {}).get(event, DEFAULT_PRIORITY)), reverse=True)
    # create plugin methods from the result
    return map(lambda info: PluginMethod(info, method, event), result)


def get_events_by_plugin(name):
    """Return all events plugin :name: hooks"""
    plugin = get_plugin_by_name(name)
    events = []
    for event_name, event in EVENT_METHODS.iteritems():
        if hasattr(plugin.instance, event):
            events.append(event_name)
    return events


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


def get_plugin_by_name(name):
    """Get plugin by name, prefered way since this structure may be changed at some point."""
    if not name in plugins:
        raise PluginDependencyError('Unknown plugin %s' % name, name)
    return plugins[name]


# TODO: separate to plugin
def print_doc(plugin_name):
    """Parameter --doc <plugin_name>"""
    found = False
    plugin = plugins.get(plugin_name, None)
    if plugin:
        found = True
        if not plugin.instance.__doc__:
            print 'Plugin %s does not have documentation' % plugin_name
        else:
            print plugin.instance.__doc__
        return
    if not found:
        print 'Could not find plugin %s' % plugin_name
