import logging
import webbrowser
from functools import partial
from pathlib import Path

from loguru import logger
from PIL import Image
from pystray import Icon, Menu, MenuItem

from flexget import __version__

logger = logger.bind(name='tray_icon')


class TrayIcon:
    def __init__(self, manager, path_to_image: Path):
        self.manager = manager
        self.path_to_image = path_to_image
        self.icon = None
        self._menu = None
        self.menu_items = []
        self.running = False
        self.add_default_menu_items()

    def add_menu_item(
        self, text: str = None, action: callable = None, menu_item: MenuItem = None, **kwargs
    ):
        if not any(v for v in (menu_item, text)):
            raise ValueError(f"Either 'text' or 'menu_item' are required")

        menu_item = menu_item or MenuItem(text=text, action=action, **kwargs)
        self.menu_items.append(menu_item)

    def add_default_menu_items(self):
        web_page = partial(webbrowser.open)
        self.add_menu_item(text=f'Flexget {__version__}', enabled=False)
        self.add_menu_item(menu_item=Menu.SEPARATOR)
        self.add_menu_item(text='Shutdown', action=self.manager.shutdown)
        self.add_menu_item(text='Reload Config', action=self.manager.load_config)
        self.add_menu_item(menu_item=Menu.SEPARATOR)
        self.add_menu_item(text='Homepage', action=partial(web_page, 'https://flexget.com/'))
        self.add_menu_item(text='Forum', action=partial(web_page, 'https://discuss.flexget.com/'))

    @property
    def menu(self) -> Menu:
        if not self._menu:
            self._menu = Menu(*self.menu_items)
        return self._menu

    def run(self):
        logging.getLogger('PIL.PngImagePlugin').setLevel(logging.INFO)  # Silence PIL noisy logging
        logging.getLogger('PIL.Image').setLevel(logging.INFO)  # Silence PIL noisy logging
        self.icon = Icon('Flexget', Image.open(self.path_to_image), menu=self.menu)
        self.running = True
        logger.verbose('Starting tray icon')
        self.icon.run()  # This call is blocking and must be done from main thread

    def stop(self):
        logger.verbose('Stopping tray icon')
        self.icon.stop()
        self.running = False
