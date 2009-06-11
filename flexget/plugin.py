from flexget import plugins as _plugins_mod
import imp, os, sys, logging

log = logging.getLogger('plugin')

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

class PluginInfo(dict):
    def __init__(self, name, item_class, parser):
        dict.__init__(self)

        self.name = name
        self.item_class = item_class

        try:
            instance = item_class()
        except Exception, e:
            raise

        self.instance = instance

        if hasattr(item_class, '__parser_options__'):
            self.options = item_class.__parser_options__
            if parser is not None:
                self.add_options(parser)

        def get_item_attr(attr_name, default):
            return hasattr(item_class, attr_name) and getattr(item_class, attr_name) or default

        self.groups = get_item_attr('__plugin_groups__', [])
        self.builtin = get_item_attr('__plugin_builtin__', False)
        self.debug = get_item_attr('__plugin_debug__', False)

        self.events = False
        for event, method in EVENT_METHODS.iteritems():
            if hasattr(instance, method):
                if callable(getattr(instance, method)):
                    self.events = True
                    break

        # parse event priorities
        self.priorities = get_item_attr('__priorities__', {})

    def add_options(self, parser):
        if not 'options' in self:
            return
        for args, kwargs in self.options:
            parser.add_option(*args, **kwargs)

    def __getattr__(self, attr):
        if attr in self:
            return self[attr]
        return dict.__getattr__(self, attr)

    def __setattr__(self, attr, value):
        self[attr] = value

class PluginMethod(object):
    def __init__(self, plugin, method_name):
        self.plugin = plugin
        self.method_name = method_name

    def __getattr__(self, attr):
        if attr in self.plugin:
            return self.plugin[attr]
        return object.__getattr__(self, attr)

    def __getitem__(self, key):
        return self.plugin[key]

    def __call__(self, *args, **kwargs):
        return getattr(self.plugin.instance, self.method_name)(*args, **kwargs)

    def __str__(self):
        return "PluginMethod: %s.%s" % (self.plugin['name'], self.method_name)

    __repr__ = __str__

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
            archless_path = os.path.join(get_python_lib(), 'flexget',
                    'plugins')
            if archless_path not in path:
                path.append(archless_path)
    return path

def load_plugins_from_dirs(dirs, parser):
    _plugins_mod.__path__ = map(_strip_trailing_sep, dirs)
    for d in dirs:
        if not d:
            continue
        log.debug('looking for plugins in %s', d)
        if os.path.isdir(d):
            load_plugins_from_dir(d, parser)

_new_event_queue = {}
def load_plugins_from_dir(d, parser):
    # Get the list of valid python suffixes for modules
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
            log.critical('Exception while loading plugin %s' % plugin)
            log.exception(e)
            raise

        plugin = getattr(_plugins_mod, name)
        for item_name, item in plugin.__dict__.iteritems():
            if hasattr(item, '__plugin__'):
                plugin_name = item.__plugin__
                if plugin_name in plugins:
                    continue
                    #log.critical('Error while registering plugin %s. %s' % (plugin_name, ('A plugin with the name %s is already registered' % plugin_name)))
                plugins[plugin_name] = PluginInfo(plugin_name, item, parser)

                if hasattr(item, '__feed_events__'):
                    for event_name, kwargs in item.__feed_events__:
                        if 'before' in kwargs and 'after' in kwargs:
                            raise RegisterException('You can only give either before or after for a event.')
                        if not 'before' in kwargs and not 'after' in kwargs:
                            raise RegisterException('You must specify either a before or after event.')
                        if event_name in EVENTS: # or event_name in self.__event_queue:
                            raise RegisterException('Event %s already exists.' % event_name)

                        def add_event(name, args):
                            if 'before' in args:
                                if not args.get('before', None) in EVENTS:
                                    return False
                            if 'after' in args:
                                if not args.get('after', None) in EVENTS:
                                    return False
                            # add method name to event -> method lookup table
                            EVENT_METHODS[name] = 'feed_'+name
                            # queue plugin loading for this type
                            PREFIXES.append(event_name)
                            # place event in event list
                            if args.get('after'):
                                EVENTS.insert(EVENTS.index(kwargs['after'])+1, name)
                            if args.get('before'):
                                EVENTS.insert(EVENTS.index(kwargs['before']), name)

                            for loaded_plugin in plugins:
                                if plugins[loaded_plugin].events:
                                    continue
                                if hasattr(plugins[loaded_plugin].instance, 'feed_' + event_name):
                                    if callable(getattr(plugins[loaded_plugin].instance, 'feed_' + event_name)):
                                        plugins[loaded_plugin].events = True
                                        continue

                            return True

                        kwargs.setdefault('class_name', item_name)
                        if not add_event(event_name, kwargs):
                            _new_event_queue[event_name] = kwargs
                            continue

                        for event_name, kwargs in _new_event_queue.items():
                            if add_event(event_name, kwargs):
                                del _new_event_queue[event_name]
    if _new_event_queue:
        for event, info in _new_event_queue.iteritems():
            log.error('plugin %s requested new event %s, but it could not be created at requested \
            point (before, after). plugin is not working properly.' % (info['class_name'], event))

plugins_loaded = False
def load_plugins(parser):
    global plugins_loaded
    if plugins_loaded:
        if parser is not None:
            for name, info in plugins.iteritems():
                info.add_options(parser)
        return
    load_plugins_from_dirs(get_standard_plugins_path(), parser)
    plugins_loaded = True

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
    for _, info in plugins.itervalues():
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
            print 'plugin %s does not have documentation' % plugin_name
        else:
            print plugin.instance.__doc__
        return
    if not found:
        print 'Could not find plugin %s' % plugin_name
