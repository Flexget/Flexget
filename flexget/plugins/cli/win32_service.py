import argparse
import os
import socket
import sys

from loguru import logger

import flexget
from flexget import options
from flexget.event import event
from flexget.terminal import console

logger = logger.bind(name='win32_service')

try:
    import servicemanager
    import win32event
    import win32service
    import win32serviceutil

    class AppServerSvc(win32serviceutil.ServiceFramework):
        _svc_name_ = 'FlexGet'
        _svc_display_name_ = 'FlexGet Daemon'
        _svc_description_ = 'Runs FlexGet tasks according to defined schedules'

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
            socket.setdefaulttimeout(60)
            self.manager = None

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            from flexget.manager import manager

            manager.shutdown(finish_queue=False)
            self.ReportServiceStatus(win32service.SERVICE_STOPPED)

        def SvcDoRun(self):
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, ''),
            )

            flexget.main(['daemon', 'start'])


except ImportError:
    pass


def do_cli(manager, options):
    import win32file
    import win32serviceutil

    if hasattr(sys, 'real_prefix'):
        # We are in a virtualenv, there is some special setup
        if not os.path.exists(os.path.join(sys.prefix, 'python.exe')):
            console('Creating a hard link to virtualenv python.exe in root of virtualenv')
            win32file.CreateHardLink(
                os.path.join(sys.prefix, 'python.exe'),
                os.path.join(sys.prefix, 'Scripts', 'python.exe'),
            )

    argv = options.args
    if options.help:
        argv = []

    # Hack sys.argv a bit so that we get a better usage message
    sys.argv[0] = 'flexget service'
    win32serviceutil.HandleCommandLine(AppServerSvc, argv=['flexget service'] + argv)


@event('options.register')
def register_parser_arguments():
    if not sys.platform.startswith('win'):
        return
    # Still not fully working. Hidden for now.
    parser = options.register_command(
        'service',
        do_cli,  # help='set up or control a windows service for the daemon',
        add_help=False,
    )
    parser.add_argument('--help', '-h', action='store_true')
    parser.add_argument('args', nargs=argparse.REMAINDER)
