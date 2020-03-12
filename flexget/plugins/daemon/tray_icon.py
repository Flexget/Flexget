from functools import partial
from pathlib import Path

from PIL import Image
from pystray import Icon, Menu, MenuItem

from flexget import ROOT_PATH, __version__
from flexget.config_schema import register_config_key
from flexget.event import event
from flexget.manager import Manager

image = ROOT_PATH / 'resources' / 'flexget.png'
disabled_action = partial(MenuItem, action=lambda icon, item: 1, enabled=False)

tray_icon_schema = {'type': 'boolean'}

tray_icon = None


class TrayIcon:
    def __init__(self, manager: Manager, path_to_image: Path = image):
        self.manager = manager
        self.icon = None
        self.menu = None
        self.path_to_image = path_to_image
        self.add_items_to_menu()

    def add_items_to_menu(self):
        version = disabled_action(__version__)
        empty_item = disabled_action('')

        shutdown = MenuItem('Shutdown', self.manager.shutdown)
        reload = MenuItem('Reload Config', self.manager.load_config)

        self.menu = Menu(version, empty_item, shutdown, reload)

    def run(self):
        self.icon = Icon('Flexget', Image.open(self.path_to_image), menu=self.menu)
        self.icon.run()

    def stop(self):
        self.icon.stop()


@event('config.register')
def register_config():
    register_config_key('tray_icon', tray_icon_schema)


@event('manager.daemon.started')
def start_tray_icon(manager):
    global tray_icon
    tray_icon = TrayIcon(manager)
    tray_icon.run()


@event('manager.shutdown')
def stop_tray_icon(manager):
    tray_icon.stop()
