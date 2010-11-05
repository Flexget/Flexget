import logging
import os
from flask import Flask, render_template, redirect, url_for, abort

log = logging.getLogger('webui')

app = Flask(__name__)
manager = None

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
    if not _home:
        abort(404)
    return redirect(url_for(_home))


@app.context_processor
def flexget_variables():
    from flask import request
    import urllib
    path = urllib.splitquery(request.path)[0]
    root = '/' + path.split('/', 2)[1]
    log.debug('root is: %s' % root)
    _update_menu(root)
    return {'menu': _menu, 'manager': manager}


# TODO: remove
def render(template, **context):
    # fill built in variables to context
#    context['menu'] = _menu
#    context['manager'] = manager
    return render_template(template, **context)


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
                
    print 'found: %s' % plugin_names

    for name in plugin_names:
        try:
            log.info('Loading UI plugin %s' % name)
            exec "import flexget.plugins.ui.%s" % name in {}
        except Exception, e:
            log.critical('Exception while loading plugin %s' % name)
            log.exception(e)
            raise


def register_menu(href, caption, order=128):
    global _menu
    _menu.append({'href': href, 'caption': caption, 'order': order})
    _menu = sorted(_menu, key=lambda item: item['order'])
    

def register_home(route):
    """Registers homepage for web ui"""
    global _home
    if _home is not None:
        raise Exception('Home is already registered')
    _home = route


def start(mg):
    global manager
    manager = mg
    # initialize
    manager.create_feeds()
    load_ui_plugins()
    app.run(host='0.0.0.0', port=5050, use_reloader=False, debug=True)
