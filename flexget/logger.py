from __future__ import absolute_import, division, unicode_literals

import logging
import logging.handlers
import string
import sys
import threading
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


_logging_configured = False
_buff_handler = None
_logging_started = False


def initialize(unit_test=False):
    """Prepare logging.
    """
    global _logging_configured, _logging_started, _buff_handler

    if _logging_configured:
        return

    warnings.simplefilter('once')
    logging.addLevelName(TRACE, 'TRACE')
    logging.addLevelName(VERBOSE, 'VERBOSE')
    _logging_configured = True

    # with unit test we want a bit simpler setup
    if unit_test:
        logging.basicConfig()
        _logging_started = True
        return

    # Store any log messages in a buffer until we `start` function is run
    logger = logging.getLogger()
    _buff_handler = logging.handlers.BufferingHandler(1000 * 1000)
    logger.addHandler(_buff_handler)
    logger.setLevel(logging.NOTSET)


def start(filename=None, level=logging.INFO, to_console=True, to_file=True):
    """After initialization, start file logging.
    """
    global _logging_started

    assert _logging_configured
    if _logging_started:
        return

    # root logger
    logger = logging.getLogger()
    if not isinstance(level, int):
        # Python logging api is horrible. This is getting the level number, which is required on python 2.6.
        level = logging.getLevelName(level)
    logger.setLevel(level)

    formatter = FlexGetFormatter()
    if to_file:
        file_handler = logging.handlers.RotatingFileHandler(filename, maxBytes=1000 * 1024, backupCount=9)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # without --cron we log to console
    if to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # flush what we have stored from the plugin initialization
    logger.removeHandler(_buff_handler)
    if _buff_handler:
        for record in _buff_handler.buffer:
            if logger.isEnabledFor(record.levelno):
                logger.handle(record)
        _buff_handler.flush()
    _logging_started = True


# Set our custom logger class as default
logging.setLoggerClass(FlexGetLogger)
