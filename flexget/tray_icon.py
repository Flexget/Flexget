from pathlib import Path

from PIL import Image
from pystray import Icon, Menu, MenuItem

from flexget import __version__


class TrayIcon:
    def __init__(self, manager, path_to_image: Path):
        self.manager = manager
        self.icon = None
        self.menu = None
        self.path_to_image = path_to_image
        self.running = False
        self.add_items_to_menu()

    def add_items_to_menu(self):
        version = MenuItem(f'Flexget {__version__}', None, enabled=False)

        shutdown = MenuItem('Shutdown', self.manager.shutdown)
        reload = MenuItem('Reload Config', self.manager.load_config)

        self.menu = Menu(version, Menu.SEPARATOR, shutdown, reload)

    def run(self):
        self.icon = Icon('Flexget', Image.open(self.path_to_image), menu=self.menu)
        self.running = True
        self.icon.run()

    def stop(self):
        self.icon.stop()
