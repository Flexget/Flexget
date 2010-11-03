import logging
import os
from flask import Flask, render_template

app = Flask(__name__)
manager = None
log = logging.getLogger('webui')

menu = [{'href': 'foobar', 
         'caption': 'Test'},
        {'href': '/help',
         'caption': 'Help'}]


# TODO: move to own plugin ...
@app.route('/')
def index():
    return render('index.html', test='foo')
    

def render(template, **context):
    # fill built in variables to context
    context['menu'] = menu
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
    menu.append({'href': href, 'caption': caption})


def start(mg):
    manager = mg
    load_ui_plugins()
    app.run(host='0.0.0.0', port=5050, use_reloader=False, debug=True)
