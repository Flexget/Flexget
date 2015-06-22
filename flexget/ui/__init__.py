from __future__ import unicode_literals, division, absolute_import
import logging
import os

from flask import send_from_directory, Flask, jsonify
from flask import Blueprint as FlaskBlueprint

from flexget.plugin import DependencyError
from flexget import __version__
from flexget.ui import plugins as ui_plugins_pkg
from flexget.webserver import register_app, register_home


log = logging.getLogger('webui')

_home = None

manager = None
_menu = []
_angular_routes = []

webui_app = Flask(__name__)
webui_app.debug = True
webui_app_root = '/ui'
webui_static_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'static')


def register_menu(href, caption, icon='fa fa-link', order=128, angular=True):
    global _menu

    if angular:
        href = '%s/#%s' % (webui_app_root, href)
    elif href.startswith('/'):
        href = '%s%s' % (webui_app_root, href)

    _menu.append({'href': href, 'caption': caption, 'icon': icon, 'order': order})
    _menu = sorted(_menu, key=lambda item: item['order'])


def register_angular_route(name, url, template_url=None, controller=None, controller_url=None):
    _angular_routes.append({
        'name': name,
        'url': url,
        'template_url': template_url,
        'controller_url': controller_url,
        'controller': controller,
    })


class Blueprint(FlaskBlueprint):

    def register_angular_route(self, name, url, template_url=None, controller=None, controller_url=None):
        # TODO: Not sure how safe this is

        # Relative URLS
        if not template_url.startswith('/'):
            template_url = "%s/static/%s/%s" % (webui_app_root, self.name, template_url)
        if not controller_url.startswith('/'):
            controller_url = "%s/static/%s/%s" % (webui_app_root, self.name, controller_url)

        register_angular_route(
            name,
            url,
            template_url=template_url,
            controller=controller,
            controller_url=controller_url
        )


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
    global manager
    manager = mgr

    load_ui_plugins()
    register_app(webui_app_root, webui_app)
    register_home('%s/' % webui_app_root)
