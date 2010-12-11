import logging
import os
import urllib
import threading
import sys
from StringIO import StringIO
from flask import Flask, redirect, url_for, abort, request
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm.session import sessionmaker
from flexget.event import fire_event
from plugin import PluginDependencyError
from Queue import Queue

log = logging.getLogger('webui')

app = Flask(__name__)
manager = None
db_session = None
server = None
executor = None

_home = None
_menu = []


class BufferQueue(Queue):

    def write(self, txt):
        self.put_nowait(txt)


class ExecThread(threading.Thread):
    """Thread that does the execution. It can accept options with an execution, and queues execs if necessary."""

    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True
        self.queue = Queue()

    def run(self):
        while True:
            kwargs = self.queue.get()
            opts = kwargs.get('options')
            output = kwargs.get('output')
            # Store the managers options and current stdout to be restored after our execution
            old_opts = manager.options
            old_stdout = sys.stdout
            if opts:
                manager.options = opts
            if output:
                sys.stdout = output
            try:
                # TODO: Update feeds instead of re-creating
                manager.create_feeds()
                manager.execute()
            finally:
                # Inform queue we are done processing this item.
                self.queue.task_done()
                # Restore manager's previous options and stdout
                manager.options = old_opts
                sys.stdout = old_stdout

    def execute(self, **kwargs):
        """
        Adds an execution to the queue.

        keyword arguments:
        options: Values from an OptionParser to be used for this execution
        output: a BufferQueue object that will be filled with output from the execution.
        """
        self.queue.put_nowait(kwargs)


def _update_menu(root):
    """Iterates trough menu navigation and sets the item selected based on the :root:"""
    for item in _menu:
        if item['href'].startswith(root):
            item['current'] = True
            log.debug('current menu item %s' % root)
        else:
            if 'current' in item:
                item.pop('current')


@app.route('/')
def start():
    """Redirect user to registered home plugin"""
    if not _home:
        abort(404)
    return redirect(url_for(_home))


@app.context_processor
def flexget_variables():
    path = urllib.splitquery(request.path)[0]
    root = '/' + path.split('/', 2)[1]
    # log.debug('root is: %s' % root)
    _update_menu(root)
    return {'menu': _menu, 'manager': manager}


def load_ui_plugins():

    # TODO: load from proper paths

    d = 'flexget/plugins/ui'

    import imp
    valid_suffixes = [suffix for suffix, mod_type, flags in imp.get_suffixes()
                      if flags in (imp.PY_SOURCE, imp.PY_COMPILED)]

    plugin_names = set()
    for f in os.listdir(d):
        path = os.path.join(d, f)
        if os.path.isfile(path):
            f_base, ext = os.path.splitext(f)
            if ext in valid_suffixes:
                if f_base == '__init__':
                    continue # don't load __init__.py again
                # elif getattr(_plugins_mod, f_base, None):
                #    log.warning('Plugin named %s already loaded' % f_base)
                plugin_names.add(f_base)

    for name in plugin_names:
        try:
            log.info('Loading UI plugin %s' % name)
            exec "import flexget.plugins.ui.%s" % name
        except PluginDependencyError, e:
            # plugin depends on another plugin that was not imported successfully
            log.error(e.value)
        except Exception, e:
            log.critical('Exception while loading plugin %s' % name)
            log.exception(e)
            raise


def register_plugin(plugin, url_prefix=None, menu=None, order=128, home=False):
    """Registers UI plugin.
    :plugin: Flask Module instance for the plugin
    """
    log.info('Registering UI plugin %s' % plugin.name)
    url_prefix = url_prefix or '/' + plugin.name
    app.register_module(plugin, url_prefix=url_prefix)
    if menu:
        register_menu(url_prefix, menu, order=order)
    if home:
        register_home(plugin.name + '.index')


def register_menu(href, caption, order=128):
    global _menu
    _menu.append({'href': href, 'caption': caption, 'order': order})
    _menu = sorted(_menu, key=lambda item: item['order'])


def register_home(route, order=128):
    """Registers homepage elements"""
    global _home
    # TODO: currently supports only one plugin
    if _home is not None:
        raise Exception('Home is already registered')
    _home = route


@app.after_request
def shutdown_session(response):
    """Remove db_session after request"""
    db_session.remove()
    return response


def start(mg):
    global manager
    manager = mg
    # create sqlachemy session for Flask usage
    global db_session
    db_session = scoped_session(sessionmaker(autocommit=False,
                                             autoflush=False,
                                             bind=manager.engine))
    if db_session is None:
        raise Exception('db_session is None')
    # initialize manager
    manager.create_feeds()
    load_ui_plugins()
    # Daemonize after we load the ui plugins as they are loading from relative paths right now
    if os.name != 'nt' and manager.options.daemon:
        if threading.activeCount() != 1:
            log.error('There are %r active threads. '
                      'Daemonizing now may cause strange failures.' %
                      threading.enumerate())
        log.info('Daemonizing.')
        newpid = daemonize()
        # Write new pid to lock file
        log.debug('Writing new pid %d to lock file %s' % (newpid, manager.lockfile))
        lockfile = file(manager.lockfile, 'w')
        try:
            lockfile.write('%d\n' % newpid)
        finally:
            lockfile.close()

    # quick hack: since ui plugins may add tables to SQLAlchemy too and they're not initialized because create
    # was called when instantiating manager .. so we need to call it again
    from flexget.manager import Base
    Base.metadata.create_all(bind=manager.engine)

    # Start the executor thread
    global executor
    executor = ExecThread()
    executor.start()
    fire_event('webui.start')

    # start Flask
    app.secret_key = os.urandom(24)
    """
    app.run(host='0.0.0.0', port=manager.options.port,
            use_reloader=manager.options.autoreload, debug=manager.options.debug)
    """

    set_exit_handler(stop_server)

    start_server()

    log.debug('server loop exited')
    fire_event('webui.stop')


def start_server():
    global server
    from cherrypy import wsgiserver
    d = wsgiserver.WSGIPathInfoDispatcher({'/': app})
    server = wsgiserver.CherryPyWSGIServer(('0.0.0.0', manager.options.port), d)

    log.debug('server %s' % server)
    try:
        server.start()
    except KeyboardInterrupt:
        stop_server()


def stop_server(*args):
    log.debug('Shutting down server')
    if server:
        server.stop()

""" werkzeug server
def start_server():
    global server
    from werkzeug.serving import make_server
    server = make_server('0.0.0.0', manager.options.port, app, threaded=True,
                         processes=1, request_handler=None,
                         passthrough_errors=False, ssl_context=None)
    log.debug('server %s' % server)
    try:
        server.serve_forever()
    except select.error:
        log.exception('select error during serve forever')

    log.debug('serve forever exited')
    fire_event('webui.stop')
    sys.exit(0)

def stop_server(*args):
    log.debug('Shutting down server')
    if server:
        threading.Thread(target=server.shutdown).start()
"""


def set_exit_handler(func):
    """Sets a callback function for term signal on windows or linux"""
    if os.name == 'nt':
        try:
            import win32api
            win32api.SetConsoleCtrlHandler(func, True)
        except ImportError:
            version = '.'.join(map(str, sys.version_info[:2]))
            raise Exception('pywin32 not installed for Python ' + version)
    else:
        import signal
        signal.signal(signal.SIGTERM, func)


def daemonize(stdin='/dev/null', stdout='/dev/null', stderr='/dev/null'):
    """Daemonizes the current process. Returns the new pid"""
    import atexit

    try:
        pid = os.fork()
        if pid > 0:
            # Don't run the exit handlers on the parent
            atexit._exithandlers = []
            # exit first parent
            sys.exit(0)
    except OSError, e:
        sys.stderr.write("fork #1 failed: %d (%s)\n" % (e.errno, e.strerror))
        sys.exit(1)

    # decouple from parent environment
    os.chdir('/')
    os.setsid()
    os.umask(0)

    # do second fork
    try:
        pid = os.fork()
        if pid > 0:
            # Don't run the exit handlers on the parent
            atexit._exithandlers = []
            # exit from second parent
            sys.exit(0)
    except OSError, e:
        sys.stderr.write("fork #2 failed: %d (%s)\n" % (e.errno, e.strerror))
        sys.exit(1)

    # redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()
    si = file(stdin, 'r')
    so = file(stdout, 'a+')
    se = file(stderr, 'a+', 0)
    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())

    return os.getpid()
