import logging
import webbrowser
from functools import partial, wraps
from pathlib import Path
from typing import Callable, List, Optional

from loguru import logger

from flexget import __version__

logger = logger.bind(name='tray_icon')

try:
    # If we are running outside of a graphical environment, these imports will fail
    from PIL import Image
    from pystray import Icon, Menu, MenuItem

    _import_success = True
except Exception as e:
    logger.debug('Could not load tray icon: {}', e)
    _import_success = False


def check_if_tray_is_active(f):
    @wraps(f)
    def wrapped(self, *args, **kwargs):
        if not self.active:
            return
        return f(self, *args, **kwargs)

    return wrapped


image_path = Path(__file__).parent / 'resources' / 'flexget.png'


class TrayIcon:
    def __init__(self, path_to_image: Path = image_path):
        # Silence PIL noisy logging
        logging.getLogger('PIL.PngImagePlugin').setLevel(logging.INFO)
        logging.getLogger('PIL.Image').setLevel(logging.INFO)

        self.path_to_image: Path = path_to_image
        self.icon: Optional['Icon'] = None
        self._menu: Optional['Menu'] = None
        self.menu_items: List['MenuItem'] = []

        self.active: bool = _import_success
        self.running: bool = False

        self.add_core_menu_items()

    @check_if_tray_is_active
    def add_menu_item(
        self,
        text: str = None,
        action: Callable = None,
        menu_item: 'MenuItem' = None,
        index: int = None,
        **kwargs,
    ):
        """
        Add a menu item byt passing its text and function, or pass a created MenuItem. Force position by sending index
        """
        if not any(v for v in (menu_item, text)):
            raise ValueError(f"Either 'text' or 'menu_item' are required")

        menu_item = menu_item or MenuItem(text=text, action=action, **kwargs)
        if index is not None:
            self.menu_items.insert(index, menu_item)
        else:
            self.menu_items.append(menu_item)

    @check_if_tray_is_active
    def add_menu_separator(self, index: int = None):
        self.add_menu_item(menu_item=Menu.SEPARATOR, index=index)

    def add_core_menu_items(self):
        open_web = partial(webbrowser.open)
        self.add_menu_item(text=f'Flexget {__version__}', enabled=False)
        self.add_menu_separator()
        self.add_menu_item(text='Homepage', action=partial(open_web, 'https://flexget.com/'))
        self.add_menu_item(text='Forum', action=partial(open_web, 'https://discuss.flexget.com/'))

    @property
    def menu(self) -> 'Menu':
        # This is lazy loaded since we'd like to delay the menu build until the tray is requested to run
        if not self._menu:
            self._menu = Menu(*self.menu_items)
        return self._menu

    @check_if_tray_is_active
    def run(self):
        """Run the tray icon. Must be run from the main thread and is blocking"""
        try:
            logger.verbose('Starting tray icon')
            self.icon = Icon('Flexget', Image.open(self.path_to_image), menu=self.menu)
            self.running = True
            self.icon.run()
        except Exception as e:
            logger.warning('Could not run tray icon: {}', e)
            self.running = False

    @check_if_tray_is_active
    def stop(self):
        if not self.running:
            return

        logger.verbose('Stopping tray icon')
        self.icon.stop()
        self.running = False


tray_icon = TrayIcon()
