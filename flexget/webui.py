import logging
import os
import urllib
from flask import Flask, redirect, url_for, abort, request
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm.session import sessionmaker
from flexget.event import fire_event
from plugin import PluginDependencyError

log = logging.getLogger('webui')

app = Flask(__name__)
manager = None
db_session = None

_home = None
_menu = []


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
    # quick hack: since ui plugins may add tables to SQLAlchemy too and they're not initialized because create
    # was called when instantiating manager .. so we need to call it again
    from flexget.manager import Base
    Base.metadata.create_all(bind=manager.engine)

    fire_event('webui.start')

    # start Flask
    app.secret_key = os.urandom(24)
    app.run(host='0.0.0.0', port=manager.options.port, threaded=True,
            use_reloader=manager.options.autoreload, debug=manager.options.debug)
