from __future__ import unicode_literals, division, absolute_import
import logging
import logging.handlers
import re
import sys
import threading
import string
import warnings

# A level more detailed than DEBUG
TRACE = 5
# A level more detailed than INFO
VERBOSE = 15


class FlexGetLogger(logging.Logger):
    """Custom logger that adds task and execution info to log records."""
    local = threading.local()

    def makeRecord(self, name, level, fn, lno, msg, args, exc_info, func=None, extra=None):
        extra = {'task': getattr(FlexGetLogger.local, 'task', '')}
        return logging.Logger.makeRecord(self, name, level, fn, lno, msg, args, exc_info, func, extra)

    def trace(self, msg, *args, **kwargs):
        """Log at TRACE level (more detailed than DEBUG)."""
        self.log(TRACE, msg, *args, **kwargs)

    def verbose(self, msg, *args, **kwargs):
        """Log at VERBOSE level (displayed when FlexGet is run interactively.)"""
        self.log(VERBOSE, msg, *args, **kwargs)


class FlexGetFormatter(logging.Formatter):
    """Custom formatter that can handle both regular log records and those created by FlexGetLogger"""
    plain_fmt = '%(asctime)-15s %(levelname)-8s %(name)-29s %(message)s'
    flexget_fmt = '%(asctime)-15s %(levelname)-8s %(name)-13s %(task)-15s %(message)s'

    def __init__(self):
        logging.Formatter.__init__(self, self.plain_fmt, '%Y-%m-%d %H:%M')

    def format(self, record):
        if hasattr(record, 'task'):
            self._fmt = self.flexget_fmt
        else:
            self._fmt = self.plain_fmt
        record.message = record.getMessage()
        if string.find(self._fmt, "%(asctime)") >= 0:
            record.asctime = self.formatTime(record, self.datefmt)
        s = self._fmt % record.__dict__
        # Replace newlines in log messages with \n
        s = s.replace('\n', '\\n')
        if record.exc_info:
            # Cache the traceback text to avoid converting it multiple times
            # (it's constant anyway)
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            if s[-1:] != "\n":
                s += "\n"
            s += record.exc_text
        return s


def set_execution(execution):
    FlexGetLogger.local.execution = execution


def set_task(task):
    FlexGetLogger.local.task = task


class PrivacyFilter(logging.Filter):
    """Edits log messages and <hides> obviously private information."""

    def __init__(self):
        self.replaces = []

        def hide(name):
            s = '([?&]%s=)\w+' % name
            p = re.compile(s)
            self.replaces.append(p)

        for param in ['passwd', 'password', 'pw', 'pass', 'passkey',
                      'key', 'apikey', 'user', 'username', 'uname', 'login', 'id']:
            hide(param)

    def filter(self, record):
        if not isinstance(record.msg, basestring):
            return False
        for p in self.replaces:
            record.msg = p.sub(r'\g<1><hidden>', record.msg)
            record.msg = record.msg
        return False

_logging_configured = False
_mem_handler = None
_logging_started = False


def initialize(unit_test=False):
    """Prepare logging.
    """
    global _logging_configured, _mem_handler

    if _logging_configured:
        return

    warnings.simplefilter('once')
    logging.addLevelName(TRACE, 'TRACE')
    logging.addLevelName(VERBOSE, 'VERBOSE')
    _logging_configured = True

    # with unit test we want a bit simpler setup
    if unit_test:
        logging.basicConfig()
        return

    # root logger
    logger = logging.getLogger()
    formatter = FlexGetFormatter()

    _mem_handler = logging.handlers.MemoryHandler(1000 * 1000, 100)
    _mem_handler.setFormatter(formatter)
    logger.addHandler(_mem_handler)

    #
    # Process commandline options, unfortunately we need to do it before argparse is available
    #

    # turn on debug level
    if '--debug' in sys.argv:
        logger.setLevel(logging.DEBUG)
    elif '--debug-trace' in sys.argv:
        logger.setLevel(TRACE)

    # without --cron we log to console
    # this must be done at initialize because otherwise there will be too much delay (user feedback) (see #1113)
    if not '--cron' in sys.argv:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        logger.addHandler(console)


def start(filename=None, level=logging.INFO, debug=False):
    """After initialization, start file logging.
    """
    global _logging_started

    assert _logging_configured
    if _logging_started:
        return

    if debug:
        handler = logging.StreamHandler()
    else:
        handler = logging.handlers.RotatingFileHandler(filename, maxBytes=1000 * 1024, backupCount=9)

    handler.setFormatter(_mem_handler.formatter)

    _mem_handler.setTarget(handler)

    # root logger
    logger = logging.getLogger()
    logger.removeHandler(_mem_handler)
    logger.addHandler(handler)
    logger.addFilter(PrivacyFilter())
    logger.setLevel(level)

    # flush what we have stored from the plugin initialization
    _mem_handler.flush()
    _logging_started = True


def flush_logging_to_console():
    """Flushes memory logger to console"""
    console = logging.StreamHandler()
    console.setFormatter(_mem_handler.formatter)
    logger = logging.getLogger()
    logger.addHandler(console)
    if len(_mem_handler.buffer) > 0:
        for record in _mem_handler.buffer:
            console.handle(record)
    _mem_handler.flush()

# Set our custom logger class as default
logging.setLoggerClass(FlexGetLogger)
