#!/usr/bin/python

from flexget.options import OptionParser
from flexget.manager import Manager
from flexget import plugin
import os
import os.path
import sys
import logging
import logging.handlers

log = logging.getLogger('main')

_logging_configured = False
_mem_handler = None
def initialize_logging(unit_test=False):
    global _logging_configured, _mem_handler

    if not _logging_configured:
        logging.addLevelName(5, 'DEBUGALL')

        if unit_test:
            _logging_configured = True
            return

        # root logger
        logger = logging.getLogger()

        # time format is same format of strftime
        log_format = ['%(asctime)-15s %(levelname)-8s %(name)-11s %(message)s', '%Y-%m-%d %H:%M']
        formatter = logging.Formatter(*log_format)

        _mem_handler = logging.handlers.MemoryHandler(1000*1000, 100)
        _mem_handler.setFormatter(formatter)
        logger.addHandler(_mem_handler)

        logger.setLevel(logging.INFO)

        _logging_configured = True

_logging_started = False
def start_logging(filename=None, level=logging.INFO, debug=False, quiet=False):
    global _logging_configured, _mem_handler, _logging_started

    if not _logging_started:
        if debug:
            hdlr = logging.StreamHandler()
        else:
            hdlr = logging.handlers.RotatingFileHandler(filename, maxBytes=1000*1024, backupCount=9)

        hdlr.setFormatter(_mem_handler.formatter)

        _mem_handler.setTarget(hdlr)

        # root logger
        logger = logging.getLogger()

        logger.removeHandler(_mem_handler)
        logger.addHandler(hdlr)

        logger.setLevel(level)

        if not debug and not quiet:
            console = logging.StreamHandler()
            console.setFormatter(hdlr.formatter)
            logger.addHandler(console)

            # flush memory handler to the console without
            # destroying the buffer
            if len(_mem_handler.buffer) > 0:
                for record in _mem_handler.buffer:
                    console.handle(record)

        # flush what we have stored from the plugin initialization
        _mem_handler.flush()

        _logging_started = True

def main():
    initialize_logging()

    parser = OptionParser()
    time_took = plugin.load_plugins(parser)

    log.debug('Plugins took %.2f seconds to load' % time_took)

    options = parser.parse_args()[0]

    if options.loglevel != 'debugall':
        log_level = getattr(logging, options.loglevel.upper())
    else:
        log_level = 5

    if os.path.exists(os.path.join(sys.path[0], '..', 'pavement.py')):
        basedir = os.path.dirname(os.path.abspath(sys.path[0]))
    else:
        basedir = sys.path[0]

    if os.path.exists(os.path.join(basedir, 'config.yml')):
        config_base = basedir
    else:
        config_base = os.path.join(os.path.expanduser('~'), '.flexget')

    start_logging(os.path.join(config_base, 'flexget.log'), log_level, quiet=options.quiet)

    manager = Manager(options, config_base)

    lockfile = os.path.join(config_base, ".%s-lock" % manager.configname)

    if os.path.exists(lockfile):
        f = file(lockfile)
        pid = f.read()
        f.close()
        print "Another process (%s) is running, will exit." % pid.strip()
        print "If you're sure there is no other instance running, delete %s" % lockfile
        sys.exit(1)

    f = file(lockfile, 'w')
    f.write("PID: %s\n" % os.getpid())
    f.close()

    try:
        if options.doc:
            plugin.print_doc(options.doc)
        elif options.list:
            plugin.print_list(options)
        elif options.failed:
            manager.print_failed()
        elif options.clear_failed:
            manager.clear_failed()
        else:
            manager.execute()
    finally:
        manager.shutdown()
        os.remove(lockfile)
