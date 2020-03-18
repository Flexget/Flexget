#!/usr/bin/python
import os
import sys
import threading

from loguru import logger

# __version__ import need to be first in order to avoid circular import within logger
from ._version import __version__  # noqa
from flexget import log
from flexget.event import event
from flexget.tray_icon import tray_icon
from flexget.manager import Manager

logger = logger.bind(name='main')
daemon_or_shutdown = threading.Event()


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
                m.start()
                if tray_icon and daemon_or_shutdown.wait(timeout=60) and manager.is_daemon:
                    tray_icon.run()
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
@event('manager.shutdown')
def try_icon_hook(manager):
    """The daemon.started event is hooked in order to make sure that we trigger the tray icon only in daemon mode.
    In addition, the shutdown event is hooked so we won't wait for the daemon to start on non daemon commands"""
    daemon_or_shutdown.set()
