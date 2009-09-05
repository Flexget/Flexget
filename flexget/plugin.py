from flexget import plugins as _plugins_mod
import imp, os, sys, logging, time

log = logging.getLogger('plugin')

__all__ = ['PluginWarning', 'PluginError', 'register_plugin',
           'register_parser_option', 'register_feed_event',
           'get_plugin_by_name', 'get_plugins_by_group',
           'get_plugins_by_event', 'get_methods_by_event']

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

def _strip_trailing_sep(path):
    return path.rstrip("\\/")

EVENTS = ['start', 'input', 'filter', 'download', 'modify', 'output', 'exit']
EVENT_METHODS = {
    'start': 'feed_start',
    'input': 'feed_input',
    'filter': 'feed_filter',
    'download': 'feed_download',
    'modify': 'feed_modify', 
    'output': 'feed_output',
    'exit': 'feed_exit',
    'abort': 'feed_abort',
    'process_start': 'process_start',
    'process_end': 'process_end'
}
PREFIXES = EVENTS + ['module', 'plugin', 'source']

plugins = {}

def register_plugin(plugin_class, name, groups=[], builtin=False, debug=False, priorities={}):
    """Registers a plugin."""
    global plugins
    if name in plugins:
        log.critical('Error while registering plugin %s. %s' % (name, ('A plugin with the name %s is already registered' % name)))
        return
    plugins[name] = PluginInfo(name, plugin_class, groups, builtin, debug, priorities)

_parser = None
_plugin_options = []
def register_parser_option(*args, **kwargs):
    """Adds a parser option to the global parser."""
    global _parser, _plugin_options
    _parser.add_option(*args, **kwargs)
    _plugin_options.append((args, kwargs))

_new_event_queue = {}
def register_feed_event(plugin_class, name, before=None, after=None):
    """Adds a new feed event to the available events."""
    global _new_event_queue, plugins
    if not before is None and not after is None:
        raise RegisterException('You can only give either before or after for a event.')
    if before is None and after is None:
        raise RegisterException('You must specify either a before or after event.')
    if name in EVENTS or name in _new_event_queue:
        raise RegisterException('Event %s already exists.' % name)

    def add_event(event_name, plugin_class, before, after):
        if not before is None and not before in EVENTS:
            return False
        if not after is None and not after in EVENTS:
            return False
        # add method name to event -> method lookup table
        EVENT_METHODS[event_name] = 'feed_'+event_name
        # queue plugin loading for this type
        PREFIXES.append(name)
        # place event in event list
        if before is None:
            EVENTS.insert(EVENTS.index(after)+1, event_name)
        if after is None:
            EVENTS.insert(EVENTS.index(before), event_name)

        for loaded_plugin in plugins:
            if plugins[loaded_plugin].events:
                continue
            if hasattr(plugins[loaded_plugin].instance, 'feed_' + name):
                if callable(getattr(plugins[loaded_plugin].instance, 'feed_' + name)):
                    plugins[loaded_plugin].events = True
                    continue
        return True

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
        for method in EVENT_METHODS.itervalues():
            if hasattr(instance, method):
                if callable(getattr(instance, method)):
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
        return "PluginInfo: %s" % self.name

    __repr__ = __str__

class PluginMethod(object):
    """
        Proxies an event for a plugin to be used as a callable object
        while also allowing accessing the plugin's attributes directly.
    """
    def __init__(self, plugin, method_name):
        self.plugin = plugin
        self.method_name = method_name

    def __getattr__(self, attr):
        if attr in self.plugin:
            return self.plugin[attr]
        return object.__getattribute__(self, attr)

    def __getitem__(self, key):
        return self.plugin[key]

    def __call__(self, *args, **kwargs):
        return getattr(self.plugin.instance, self.method_name)(*args, **kwargs)

    def __str__(self):
        return "PluginMethod: %s.%s" % (self.plugin['name'], self.method_name)

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
    valid_suffixes = [suffix for suffix, mod_type, flags in imp.get_suffixes()
                              if flags in (imp.PY_SOURCE, imp.PY_COMPILED)]
    plugin_names = set()
    for f in os.listdir(d):
        path = os.path.join(d, f)
        if os.path.isfile(path):
            f_base, ext = os.path.splitext(f)
            path_parts = f_base.split('_')
            if ext in valid_suffixes:
                if f_base == '__init__':
                    continue # don't load __init__.py again
                elif getattr(_plugins_mod, f_base, None):
                    log.info('Plugin named %s already loaded' % f_base)
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
            point (before, after). plugin is not working properly.' % (args[0], event))

plugins_loaded = False
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
    method = EVENT_METHODS[event]
    for info in plugins.itervalues():
        instance = info.instance
        if not hasattr(instance, method):
            continue
        if callable(getattr(instance, method)):
            result.append(info)
    result.sort(lambda x, y: cmp(x.get('priorities', {}).get(event, 0), \
                                 y.get('priorities', {}).get(event, 0)), reverse=True)
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
    result.sort(lambda x, y: cmp(x.get('priorities', {}).get(event, 0), \
                                 y.get('priorities', {}).get(event, 0)), reverse=True)
    result = map(lambda info: PluginMethod(info, method), result)
    return result

def get_plugins_by_group(group):
    """Return all plugins with in specified group."""
    res = []
    for info in plugins.itervalues():
        if group in info.get('groups'):
            res.append(info)
    return res

def get_plugin_by_name(name):
    """Get plugin by name, prefered way since this structure may be changed at some point."""
    if not name in plugins:
        raise Exception('Unknown plugin %s' % name)
    return plugins[name]

def print_list(options):
    # TODO: rewrite!
    """Parameter --list"""
    print '-'*60
    print '%-20s%-30s%s' % ('Keyword', 'Roles', '--doc')
    print '-'*60
    plugins = []
    roles = {}
    for event in EVENTS:
        try:
            ml = get_plugins_by_event(event)
        except:
            continue
        for m in ml:
            dupe = False
            for plugin in plugins:
                if plugin['name'] == m['name']: 
                    dupe = True
            if not dupe:
                plugins.append(m)
        # build roles list
        for m in ml:
            if m['name'] in roles:
                roles[m['name']].append(event)
            else:
                roles[m['name']] = [event]
    for plugin in plugins:
        # do not include test classes, unless in debug mode
        if plugin.get('debug_plugin', False) and not options.debug:
            continue
        doc = 'Yes'
        if not plugin.instance.__doc__: 
            doc = 'No'
        print '%-20s%-30s%s' % (plugin['name'], ', '.join(roles[plugin['name']]), doc)
    print '-'*60

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
