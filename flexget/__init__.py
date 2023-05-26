#!/usr/bin/python
import os
import sys
from typing import Sequence

# __version__ import need to be first in order to avoid circular import within logger
from ._version import __version__  # noqa

# isort: split
from flexget import log
from flexget.manager import Manager


def main(args: Sequence[str] = None):
    """Main entry point for Command Line Interface"""

    if args is None:
        args = sys.argv[1:]
    try:
        log.initialize()

        try:
            manager = Manager(args)
        except (OSError, ValueError) as e:
            options = Manager.parse_initial_options(args)
            log.start(level=options.loglevel, to_file=False)
            if _is_debug():
                import traceback

                traceback.print_exc()
            else:
                print('Could not instantiate manager: %s' % e, file=sys.stderr)
            sys.exit(1)
        else:
            log.start(
                manager.log_filename,
                manager.options.loglevel,
                to_file=manager.check_ipc_info() is None,
                to_console=not manager.options.cron,
            )

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
                manager.start()
        except (OSError, ValueError) as e:
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


def _is_debug() -> bool:
    return any(
        arg in ['debug', '--debug', '--loglevel=trace', '--loglevel=debug']
        for arg in [a.lower() for a in sys.argv]
    )
