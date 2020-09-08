import os
import sys

from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.plugin import DependencyError, PluginWarning

plugin_name = 'toast'

logger = logger.bind(name=plugin_name)


class NotifyToast:
    """
    Sends messages via local notification system. You must have a notification system like dbus for Linux.
    Preliminary support for Windows notifications. Not heavily tested yet.

    Examples::

      notify:
        entries:
          via:
            - toast: yes

      notify:
        entries:
          via:
            - toast:
                timeout: 5
    """

    schema = {
        'anyOf': [
            {'type': 'boolean', 'enum': [True]},
            {
                'type': 'object',
                'properties': {'timeout': {'type': 'integer'}, 'url': {'type': 'string'}},
                'additionalProperties': False,
            },
        ]
    }

    def __init__(self):
        self.windows_classAtom = None

    def prepare_config(self, config):
        if not isinstance(config, dict):
            config = {}
        config.setdefault('timeout', 4)
        config.setdefault('url', '')
        return config

    def mac_notify(self, title, message, config):
        config = self.prepare_config(config)
        try:
            from pync import Notifier
        except ImportError as e:
            logger.debug('Error importing pync: {}', e)
            raise DependencyError(plugin_name, 'pync', 'pync module required. ImportError: %s' % e)

        icon_path = None
        try:
            import flexget.ui

            icon_path = os.path.join(flexget.ui.__path__[0], 'src', 'favicon.ico')
        except Exception as e:
            logger.debug('Error trying to get flexget icon from webui folder: {}', e)

        try:
            Notifier.notify(
                message,
                subtitle=title,
                title='FlexGet Notification',
                appIcon=icon_path,
                timeout=config['timeout'],
                open=config.get('url'),
            )
        except Exception as e:
            raise PluginWarning('Cannot send a notification: %s' % e)

    def linux_notify(self, title, message, config):
        config = self.prepare_config(config)
        try:
            from gi.repository import Notify
        except ImportError as e:
            logger.debug('Error importing Notify: {}', e)
            raise DependencyError(
                plugin_name, 'gi.repository', 'Notify module required. ImportError: %s' % e
            )

        if not Notify.init("Flexget"):
            raise PluginWarning('Unable to init libnotify.')

        n = Notify.Notification.new(title, message, None)
        timeout = config['timeout'] * 1000
        n.set_timeout(timeout)

        if not n.show():
            raise PluginWarning('Unable to send notification for %s' % title)

    def windows_notify(self, title, message, config):
        config = self.prepare_config(config)
        try:
            from win32api import GetModuleHandle, PostQuitMessage
            from win32con import (
                CW_USEDEFAULT,
                IDI_APPLICATION,
                IMAGE_ICON,
                LR_DEFAULTSIZE,
                LR_LOADFROMFILE,
                WM_DESTROY,
                WM_USER,
                WS_OVERLAPPED,
                WS_SYSMENU,
            )
            from win32gui import (
                NIF_ICON,
                NIF_INFO,
                NIF_MESSAGE,
                NIF_TIP,
                NIM_ADD,
                NIM_DELETE,
                NIM_MODIFY,
                WNDCLASS,
                CreateWindow,
                DestroyWindow,
                LoadIcon,
                LoadImage,
                RegisterClass,
                Shell_NotifyIcon,
                UpdateWindow,
            )
        except ImportError:
            raise DependencyError(
                plugin_name,
                'pypiwin32',
                'pywin32 module is required for desktop notifications on '
                'windows. You can install it with `pip install pypiwin32`',
            )

        # Register the window class.
        wc = WNDCLASS()
        hinst = wc.hInstance = GetModuleHandle(None)
        wc.lpszClassName = "FlexGetTaskbar"
        if not self.windows_classAtom:
            self.windows_classAtom = RegisterClass(wc)
        style = WS_OVERLAPPED | WS_SYSMENU
        hwnd = CreateWindow(
            self.windows_classAtom,
            "Taskbar",
            style,
            0,
            0,
            CW_USEDEFAULT,
            CW_USEDEFAULT,
            0,
            0,
            hinst,
            None,
        )
        UpdateWindow(hwnd)

        hicon = LoadIcon(0, IDI_APPLICATION)
        # Hackily grab the icon from the webui if possible
        icon_flags = LR_LOADFROMFILE | LR_DEFAULTSIZE
        try:
            import flexget.ui

            icon_path = os.path.join(flexget.ui.__path__[0], 'src', 'favicon.ico')
            hicon = LoadImage(hinst, icon_path, IMAGE_ICON, 0, 0, icon_flags)
        except Exception as e:
            logger.debug('Error trying to get flexget icon from webui folder: {}', e)

        # Taskbar icon
        flags = NIF_ICON | NIF_MESSAGE | NIF_TIP | NIF_INFO
        nid = (
            hwnd,
            0,
            flags,
            WM_USER + 20,
            hicon,
            "FlexGet Notification",
            message,
            config['timeout'] * 1000,
            title,
        )
        Shell_NotifyIcon(NIM_ADD, nid)

    if sys.platform.startswith('win'):
        notify = windows_notify
    elif sys.platform == 'darwin':
        notify = mac_notify
    else:
        notify = linux_notify


@event('plugin.register')
def register_plugin():
    plugin.register(NotifyToast, plugin_name, api_ver=2, interfaces=['notifiers'])
