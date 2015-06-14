from __future__ import unicode_literals, division, absolute_import
import logging
import os

import flask_menu as menu
from flask import send_from_directory, Flask

from flexget.plugin import DependencyError
from flexget import __version__
from flexget.ui import plugins as ui_plugins_pkg
from flexget.webserver import register_app, register_home


log = logging.getLogger('webui')

_home = None

manager = None
config = {}

webui_app = Flask(__name__)
webui_app.debug = True

menu.Menu(app=webui_app)


@webui_app.route('/userstatic/<path:filename>')
def user_static(filename):
    return send_from_directory(os.path.join(manager.config_base, 'userstatic'), filename)


@webui_app.context_processor
def flexget_variables():
    return {
        'version': __version__
    }


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
    register_app('/ui', webui_app)
    register_home('/ui/')
