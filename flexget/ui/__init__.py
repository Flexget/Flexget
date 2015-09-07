from __future__ import unicode_literals, division, absolute_import
import logging
import os

from flask import send_from_directory, Flask, jsonify
from flask import Blueprint as FlaskBlueprint

from flexget.plugin import DependencyError
from flexget import __version__
from flexget.ui import plugins as ui_plugins_pkg
from flexget.webserver import register_app, register_home
from flask.ext.assets import Environment, Bundle
from flask_compress import Compress

log = logging.getLogger('webui')

_home = None
_menu = []
_angular_routes = []
_asset_registry = {}

manager = None
assets = None

webui_app = Flask(__name__)
Compress(webui_app)
webui_app.url_path = '/ui'
webui_static_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'static')


def register_asset_type(name, output_file, filters=None):
    _asset_registry[name] = {'out': output_file, 'filters': filters, 'items': []}


register_asset_type('js_all', 'js/flexget.min.js', filters='rjsmin')
register_asset_type('css_all', 'css/flexget.min.css', filters='cssmin')


def register_asset(asset_type, name, f, order=128, bp=None):
    global _asset_registry
    name = name.lower()

    if asset_type not in _asset_registry:
        raise KeyError('asset registry %s does not exist' % asset_type)

    registry = _asset_registry[asset_type]

    for item in registry['items']:
        if item['name'] == name:
            log.error('%s is already registered to %s' % registry['items'][name]['file'])
            return

    if bp:
        f = '%s/%s' % (bp.name, f)

    registry['items'].append({'name': name, 'file': f, 'order': order})
    registry['items'] = sorted(registry['items'], key=lambda item: item['order'])


def register_js(name, f, order=128, bp=None):
    """ Shortcut to register javascript files. Calls register_asset """
    register_asset('js_all', name, f, order=order, bp=bp)


def register_css(name, f, order=128, bp=None):
    """ Shortcut to register javascript files. Calls register_asset """
    register_asset('css_all', name, f, order=order, bp=bp)


def register_font(name, f, order=128, bp=None):
    """ Shortcut to register font files. Calls register_asset """
    register_asset('font_all', name, f, order=order, bp=bp)


@webui_app.before_first_request
def _load_assets():
    for name, asset_registry in _asset_registry.iteritems():
        asset_files = [item['file'] for item in asset_registry['items']]
        asset_bundle = Bundle(*asset_files, filters=asset_registry['filters'], output=asset_registry['out'])
        assets.register(name, asset_bundle)


# Required core js files
register_js('angular', 'js/angularjs/angular.min.js', order=10)
register_js('angular-material', 'js/angular-material.min.js', order=11)
register_js('angular-ui-router', 'js/angular-ui-router.min.js', order=11)
register_js('angular-sanitize', 'js/angularjs/angular-sanitize.min.js', order=11)
register_js('angular-animate', 'js/angularjs/angular-animate.min.js', order=11)
register_js('angular-aria', 'js/angularjs/angular-aria.min.js', order=11)
register_js('angular-filter', 'js/angular-filter.min.js', order=11)
register_js('flexget', 'js/flexget.js', order=20)
register_js('common-utils', 'js/common/utils.js', order=20)
register_js('common-directives', 'js/common/directives.js', order=20)
register_js('common-controllers', 'js/common/controllers.js', order=20)
register_js('common-services', 'js/common/services.js', order=20)
register_js('ui-grid', 'js/ui-grid.min.js', order=20)
register_js('tv4', 'js/tv4.min.js', order=25)
register_js('ObjectPath', 'js/schema-form/ObjectPath.js', order=25)
register_js('schema-form', 'js/schema-form/schema-form.js', order=25)
register_js('bootstrap-decorator', 'js/schema-form/bootstrap-decorator.js', order=26)

# Register core css files
register_css('angular-material', 'css/angular-material.min.css', order=1)
register_css('ng-table', 'css/ui-grid.min.css', order=20)
register_css('flexget', 'css/flexget.css', order=30)


def register_menu(href, caption, icon='fa fa-link', order=128, angular=True):
    global _menu

    if angular:
        href = '%s/#%s' % (webui_app.url_path, href)
    elif href.startswith('/'):
        href = '%s%s' % (webui_app.url_path, href)

    _menu.append({'href': href, 'caption': caption, 'icon': icon, 'order': order})
    _menu = sorted(_menu, key=lambda item: item['order'])


def register_angular_route(name, url, template_url=None, controller=None):
    _angular_routes.append({
        'name': name,
        'url': url,
        'template_url': template_url,
        'controller': controller,
    })


class Blueprint(FlaskBlueprint):

    def register_js(self, name, f, order=128):
        register_asset('js_all', name, f, order=order, bp=self)

    def register_css(self, name, f, order=128):
        register_asset('css_all', name, f, order=order, bp=self)

    def register_angular_route(self, name, url, template_url=None, controller=None):
        # Relative URLS
        if not template_url.startswith('/'):
            template_url = "%s/static/%s/%s" % (webui_app.url_path, self.name, template_url)

        # Append blueprint name to create nested states
        name = '%s.%s' % (self.name, name) if name else self.name

        register_angular_route(name, url, template_url=template_url, controller=controller)


@webui_app.context_processor
def flexget_variables():
    return {
        'version': __version__,
        'menu': _menu,
    }


@webui_app.route('/static/<plugin>/<path:path>')
def static_server(plugin, path):
    bp = webui_app.blueprints.get(plugin)
    if bp:
        return send_from_directory(bp.static_folder, path)
    else:
        return send_from_directory(webui_static_path, '%s/%s' % (plugin, path))


@webui_app.route('/userstatic/<path:filename>')
def user_static_server(filename):
    return send_from_directory(os.path.join(manager.config_base, 'userstatic'), filename)


@webui_app.route('/routes')
def routes():
    return jsonify({'routes': _angular_routes})


def _strip_trailing_sep(path):
    return path.rstrip("\\/")


def _get_standard_ui_plugins_path():
    """
    :returns: List of directories where ui plugins should be tried to load from.
    """

    # Get basic path from environment
    paths = []

    env_path = os.environ.get('FLEXGET_UI_PLUGIN_PATH')
    if env_path:
        paths = [path for path in env_path.split(os.pathsep) if os.path.isdir(path)]

    # Add flexget.ui.plugins directory (core ui plugins)
    import flexget.ui.plugins
    paths.append(flexget.ui.plugins.__path__[0])
    return paths


def _load_ui_plugins_from_dirs(dirs):

    # Ensure plugins can be loaded via flexget.ui.plugins
    ui_plugins_pkg.__path__ = map(_strip_trailing_sep, dirs)

    plugins = set()
    for d in dirs:
        for f in os.listdir(d):
            path = os.path.join(d, f, '__init__.py')
            if os.path.isfile(path):
                plugins.add(f)

    for plugin in plugins:
        name = plugin.split(".")[-1]
        try:
            log.debug('Loading UI plugin %s' % name)
            exec "import flexget.ui.plugins.%s" % plugin
        except DependencyError as e:
            # plugin depends on another plugin that was not imported successfully
            log.error(e.message)
        except EnvironmentError as e:
            log.info('Plugin %s: %s' % (name, str(e)))
        except Exception as e:
            log.critical('Exception while loading plugin %s' % name)
            log.exception(e)
            raise


def load_ui_plugins():

    # Add flexget.plugins directory (core plugins)
    ui_plugin_dirs = _get_standard_ui_plugins_path()

    user_plugin_dir = os.path.join(manager.config_base, 'ui_plugins')
    if os.path.isdir(user_plugin_dir):
        ui_plugin_dirs.append(user_plugin_dir)

    _load_ui_plugins_from_dirs(ui_plugin_dirs)


def register_plugin(blueprint):
    """
    Registers UI plugin.

    :plugin: :class:`flask.Blueprint` object for this plugin.
    """
    # Set up some defaults if the plugin did not already specify them
    if blueprint.url_prefix is None:
        blueprint.url_prefix = '/' + blueprint.name
    if not blueprint.template_folder and os.path.isdir(os.path.join(blueprint.root_path, 'templates')):
        blueprint.template_folder = 'templates'
    if not blueprint.static_folder and os.path.isdir(os.path.join(blueprint.root_path, 'static')):
        blueprint.static_folder = 'static'
    log.verbose('Registering UI plugin %s' % blueprint.name)
    webui_app.register_blueprint(blueprint)


def register_web_ui(mgr):
    global manager, assets
    manager = mgr

    assets_cache = os.path.join(manager.config_base, '.webassets-cache')
    user_static_folder = os.path.join(manager.config_base, 'userstatic')

    for folder in [assets_cache, user_static_folder]:
        if not os.path.isdir(folder):
            os.mkdir(folder)

    assets = Environment(webui_app)
    assets.directory = user_static_folder
    assets.cache = assets_cache
    assets.url = '%s/userstatic' % webui_app.url_path

    # TODO: Better way to do this?
    if 'debug' in manager.args:
        assets.debug = True

    load_ui_plugins()

    register_app(webui_app.url_path, webui_app)
    register_home('%s/' % webui_app.url_path)
