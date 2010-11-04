import logging
import os
from flask import Flask, render_template

log = logging.getLogger('webui')

app = Flask(__name__)
manager = None

_menu = []


class menu_current(object):
    """Decorator which updates menu items current flag to the given value"""

    def __init__(self, name):
        self.name = name
        
    def __call__(self, f):
        log.debug('updating current menu #1')

        def wrapped_f(*args, **kwargs):
            log.debug('updating current menu #2')
            for item in _menu:
                if item['caption'].lower() == self.name.lower():
                    item['current'] = True
                    log.debug('current menu item %s' % self.name)
                else:
                    if 'current' in item:
                        item.pop('current')
            return f(*args, **kwargs)
        return wrapped_f


def render(template, **context):
    # fill built in variables to context
    context['menu'] = _menu
    context['manager'] = manager
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


def start(mg):
    global manager
    manager = mg
    # initialize
    manager.create_feeds()
    load_ui_plugins()
    app.run(host='0.0.0.0', port=5050, use_reloader=False, debug=True)
