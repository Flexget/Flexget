#!/usr/bin/python
import os
import sys
import threading
from pathlib import Path
from time import sleep

# __version__ import need to be first in order to avoid circular import within logger
from ._version import __version__  # noqa
from flexget import log
from flexget.manager import Manager
from flexget.event import event

manager_loaded = False


def init_tray_icon(manager: Manager):
    if os.environ.get('GITHUB_ACTIONS'):
        # We cannot init tray action via our CI since it requires X on linux
        return
    from flexget.tray_icon import TrayIcon

    image_path = Path('flexget') / 'resources' / 'flexget.png'
    tray = TrayIcon(manager=manager, path_to_image=image_path)
    return tray


def main(args=None):
    """Main entry point for Command Line Interface"""

    try:
        log.initialize()

        try:
            manager = Manager(args)
        except (IOError, ValueError) as e:
            if _is_debug():
                import traceback

                traceback.print_exc()
            else:
                print('Could not instantiate manager: %s' % e, file=sys.stderr)
            sys.exit(1)

        try:
            if manager.options.profile:
                try:
                    import cProfile as profile
                except ImportError:
                    import profile
                profile.runctx(
                    'manager.start()',
                    globals(),
                    locals(),
                    os.path.join(manager.config_base, manager.options.profile),
                )
            else:
                m = threading.Thread(target=manager.start, daemon=True)
                tray = init_tray_icon(manager)
                manager.tray = tray
                m.start()
                if tray:
                    while not manager_loaded:
                        sleep(1)
                    if manager.is_daemon:
                        tray.run()
                m.join()
        except (IOError, ValueError) as e:
            if _is_debug():
                import traceback

                traceback.print_exc()
            else:
                print('Could not start manager: %s' % e, file=sys.stderr)

            sys.exit(1)
    except KeyboardInterrupt:
        if _is_debug():
            import traceback

            traceback.print_exc()

        print('Killed with keyboard interrupt.', file=sys.stderr)
        sys.exit(1)


def _is_debug():
    return any(
        arg in ['debug', '--debug', '--loglevel=trace', '--loglevel=debug']
        for arg in [a.lower() for a in sys.argv]
    )


@event('manager.daemon.started')
def set_manager_started(manager):
    # This is used since we have to wait until manager is loaded before deciding if manager runs a
    # daemon or not, and we cant run the tray by hooking this event since it has to run on the main thread
    global manager_loaded
    manager_loaded = True
