from __future__ import unicode_literals, division, absolute_import
import logging
import os
import json
import fnmatch
import glob

from flask import send_from_directory, Flask, abort, render_template

from flexget.webserver import register_app, register_home
from flask.ext.assets import Environment, Bundle
from flask_compress import Compress


log = logging.getLogger('webui')

_home = None
_asset_registry = {}
_plugins = {}

manager = None
assets = None

webui_app = Flask(__name__)
Compress(webui_app)
webui_app.url_path = '/ui'
webui_path = os.path.dirname(os.path.realpath(__file__))


def register_asset_type(name, output_file, filters=None):
    _asset_registry[name] = {'out': output_file, 'filters': filters, 'items': []}


register_asset_type('vendor_js', 'js/vendor.min.js', filters='rjsmin')
register_asset_type('vendor_css', 'css/vendor.min.css')

register_asset_type('flexget_js', 'js/flexget.min.js', filters='rjsmin')
register_asset_type('flexget_css', 'css/flexget.min.css', filters='cssmin')

register_asset_type('plugins_js', 'js/plugins.min.js', filters='rjsmin')
register_asset_type('plugins_css', 'css/plugins.min.css', filters='cssmin')


def register_asset(asset_type, asset):
    global _asset_registry

    if asset_type not in _asset_registry:
        raise KeyError('asset registry %s does not exist' % asset_type)

    registry = _asset_registry[asset_type]
    registry['items'].append(asset)


@webui_app.before_first_request
def _load_assets():
    for name, asset_registry in _asset_registry.iteritems():
        asset_files = [item for item in asset_registry['items']]
        asset_bundle = Bundle(*asset_files, filters=asset_registry['filters'], output=asset_registry['out'])
        assets.register(name, asset_bundle)


@webui_app.route('/templates/<path:filename>')
def templates_server(filename):
    return send_from_directory(os.path.join(webui_path, 'templates'), filename)


@webui_app.route('/images/<path:filename>')
def images_server(filename):
    return send_from_directory(os.path.join(webui_path, 'images'), filename)


@webui_app.route('/vendor/<path:filename>')
def vendor_server(filename):
    return send_from_directory(os.path.join(webui_path, 'vendor'), filename)


@webui_app.route('/plugin/<plugin>/<path:path>')
def plugin_static_server(plugin, path):
    if plugin in _plugins and path.split("/")[0] in ['static', 'js', 'css']:
        return send_from_directory(os.path.join(_plugins[plugin]['path']), path)
    return abort(404)


@webui_app.route('/cache/<path:filename>')
def user_static_server(filename):
    return send_from_directory(os.path.join(manager.config_base, '.webassets-cache'), filename)


@webui_app.route('/')
def index():
    return render_template('index.html')


def _find(path, f):
    matches = []
    for root, dir_names, file_names in os.walk(path):
        for filename in fnmatch.filter(file_names, f):
            matches.append(os.path.join(root, filename))
    return matches


def _strip_trailing_sep(path):
    return path.rstrip('\\/')


def _get_plugin_paths():
    # Standard plugins
    plugins_paths = [os.path.join(os.path.dirname(os.path.realpath(__file__)), 'plugins')]

    # Additional plugin paths
    if os.environ.get('FLEXGET_UI_PLUGIN_PATH'):
        for path in os.environ.get('FLEXGET_UI_PLUGIN_PATH').split(os.pathsep):
            if os.path.isdir(path):
                plugins_paths.append(path)

    user_plugin_dir = os.path.join(manager.config_base, 'plugins', 'ui')
    if os.path.isdir(user_plugin_dir):
        plugins_paths.append(user_plugin_dir)

    return plugins_paths


def _register_plugin(plugin_path):
    plugin_config = os.path.join(plugin_path, 'plugin.json')

    if not os.path.isfile(plugin_config):
        log.warn('Unable to load plugin %s missing' % plugin_config)
        return
    try:
        with open(plugin_config, 'r') as f:
            config = json.load(f)
    except IOError as e:
        log.error('Error loading plugin config %s as %s' % (plugin_config, str(e)))
        return
    except ValueError as e:
        log.error('Invalid plugin config %s as %s' % (plugin_config, str(e)))
        return

    name = config.get('name')
    if not name:
        log.error('Error loading plugin missing name in ' % plugin_config)
        return

    if name in _plugins:
        log.error('Error loading plugin %s with name %s as it\'s already registered ' % (plugin_config, name))
        return

    version = config.get('version', '1.0')
    _plugins[name] = {'path': plugin_path, 'config': config, version: version}

    # Register CSS/SASS assets
    """
    if config.get('sass'):
        sass_path = os.path.normpath(os.path.join(plugin_path, 'sass'))
        sass_file = os.path.join(sass_path, config['sass'])
        libsass = get_filter('libsass', includes=[os.path.join(webui_path, 'sass'), sass_path])
        register_asset('plugins_css', Bundle(sass_file, output='css/%s.css' % name, filters=(libsass,)))
    """

    css_path = os.path.join(plugin_path, 'css')
    if os.path.isdir(css_path):
        for css_file in _find(css_path, "*.css"):
            register_asset('plugins_css', css_file)

    # Register JS assets
    if config.get('js'):
        for js_file in config['js']:
            js_file = '%s.js' % os.path.normpath(os.path.join(plugin_path, 'js', js_file))
            register_asset('plugins_js', js_file)
    else:
        js_path = os.path.join(plugin_path, 'js')
        if os.path.isdir(js_path):
            # Register JS assets
            for js_file in _find(js_path, "*.js"):
                register_asset('plugins_js', js_file)


def _load_ui_plugins_from_dir(path):
    for plugin in os.listdir(path):
        _register_plugin(os.path.join(path, plugin))


def load_ui_plugins():
    plugin_paths = _get_plugin_paths()

    for path in plugin_paths:
        _load_ui_plugins_from_dir(path)


def load_assets():

    with open(os.path.join(webui_path, 'config.json'), 'r') as f:
        config = json.load(f)

    # Register JS assets
    for js_glob in config['flexget_js']:
        for js_file in glob.glob(os.path.join(webui_path, os.path.normpath(js_glob))):
            register_asset('flexget_js', js_file)

    for js_file in config['vendor_js']:
        register_asset('vendor_js', os.path.normpath(os.path.join(webui_path, js_file)))

    # Register CSS/SCSS
    for css_file in config['vendor_css']:
        register_asset('vendor_css', os.path.normpath(os.path.join(webui_path, css_file)))

    sass_file = os.path.join(webui_path, 'css', 'flexget.scss')
    register_asset('flexget_css', Bundle(sass_file, output='css/flexget.css', filters='pyscss'))


def register_web_ui(mgr):
    global manager, assets
    manager = mgr

    assets_cache = os.path.join(manager.config_base, '.webassets-cache')

    if not os.path.isdir(assets_cache):
        os.mkdir(assets_cache)

    assets = Environment(webui_app)
    assets.directory = assets_cache

    for p in _get_plugin_paths():
        assets.append_path(p, url="%s/plugin" % webui_app.url_path)

    assets.cache = assets_cache
    assets.url = '%s/cache' % webui_app.url_path
    if 'debug' in manager.args:
        assets.debug = True

    load_assets()
    load_ui_plugins()

    register_app(webui_app.url_path, webui_app)
    register_home('%s/' % webui_app.url_path)
