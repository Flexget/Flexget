from __future__ import unicode_literals, division, absolute_import, print_function
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import codecs
import collections
import contextlib
import logging
import logging.handlers
import sys
import threading
import uuid
import warnings

from flexget import __version__
from flexget.utils.tools import io_encoding

# A level more detailed than DEBUG
TRACE = 5
# A level more detailed than INFO
VERBOSE = 15

# Stores `task`, logging `session_id`, and redirected `output` stream in a thread local context
local_context = threading.local()


def get_level_no(level):
    if not isinstance(level, int):
        # Cannot use getLevelName here as in 3.4.0 it returns a string.
        level = level.upper()
        if level == 'TRACE':
            level = TRACE
        elif level == 'VERBOSE':
            level = VERBOSE
        else:
            level = getattr(logging, level)

    return level


@contextlib.contextmanager
def task_logging(task):
    """Context manager which adds task information to log messages."""
    old_task = getattr(local_context, 'task', '')
    local_context.task = task
    try:
        yield
    finally:
        local_context.task = old_task


class SessionFilter(logging.Filter):
    def __init__(self, session_id):
        self.session_id = session_id

    def filter(self, record):
        return getattr(record, 'session_id', None) == self.session_id


@contextlib.contextmanager
def capture_output(stream, loglevel=None):
    """Context manager which captures all log and console output to given `stream` while in scope."""
    root_logger = logging.getLogger()
    old_level = root_logger.getEffectiveLevel()
    old_id = getattr(local_context, 'session_id', None)
    # Keep using current, or create one if none already set
    local_context.session_id = old_id or uuid.uuid4()
    old_output = getattr(local_context, 'output', None)
    old_loglevel = getattr(local_context, 'loglevel', None)
    streamhandler = logging.StreamHandler(stream)
    streamhandler.setFormatter(FlexGetFormatter())
    streamhandler.addFilter(SessionFilter(local_context.session_id))
    if loglevel is not None:
        loglevel = get_level_no(loglevel)
        streamhandler.setLevel(loglevel)
        # If requested loglevel is lower than the root logger is filtering for, we need to turn it down.
        # All existing handlers should have their desired level set and not be affected.
        if not root_logger.isEnabledFor(loglevel):
            root_logger.setLevel(loglevel)
    local_context.output = stream
    local_context.loglevel = loglevel
    root_logger.addHandler(streamhandler)
    try:
        yield
    finally:
        root_logger.removeHandler(streamhandler)
        root_logger.setLevel(old_level)
        local_context.session_id = old_id
        local_context.output = old_output
        local_context.loglevel = old_loglevel


def get_capture_stream():
    """If output is currently being redirected to a stream, returns that stream."""
    return getattr(local_context, 'output', None)


def get_capture_loglevel():
    """If output is currently being redirected to a stream, returns declared loglevel for that stream."""
    return getattr(local_context, 'loglevel', None)


class RollingBuffer(collections.deque):
    """File-like that keeps a certain number of lines of text in memory."""

    def write(self, line):
        self.append(line)


class FlexGetLogger(logging.Logger):
    """Custom logger that adds trace and verbose logging methods, and contextual information to log records."""

    def makeRecord(self, name, level, fn, lno, msg, args, exc_info, func, extra, *exargs):
        extra = extra or {}
        extra.update(
            task=getattr(local_context, 'task', ''),
            session_id=getattr(local_context, 'session_id', ''))
        # Replace newlines in log messages with \n
        if isinstance(msg, str):
            msg = msg.replace('\n', '\\n')

        return logging.Logger.makeRecord(self, name, level, fn, lno, msg, args, exc_info, func, extra, *exargs)

    def trace(self, msg, *args, **kwargs):
        """Log at TRACE level (more detailed than DEBUG)."""
        self.log(TRACE, msg, *args, **kwargs)

    def verbose(self, msg, *args, **kwargs):
        """Log at VERBOSE level (displayed when FlexGet is run interactively.)"""
        self.log(VERBOSE, msg, *args, **kwargs)


class FlexGetFormatter(logging.Formatter):
    """Custom formatter that can handle both regular log records and those created by FlexGetLogger"""
    flexget_fmt = '%(asctime)-15s %(levelname)-8s %(name)-13s %(task)-15s %(message)s'

    def __init__(self):
        logging.Formatter.__init__(self, self.flexget_fmt, '%Y-%m-%d %H:%M')

    def format(self, record):
        if not hasattr(record, 'task'):
            record.task = ''
        return logging.Formatter.format(self, record)


_logging_configured = False
_buff_handler = None
_logging_started = False
# Stores the last 50 debug messages
debug_buffer = RollingBuffer(maxlen=50)


def initialize(unit_test=False):
    """Prepare logging.
    """
    global _logging_configured, _logging_started, _buff_handler

    if _logging_configured:
        return

    if 'dev' in __version__:
        warnings.filterwarnings('always', category=DeprecationWarning, module='flexget.*')
    warnings.simplefilter('once', append=True)
    logging.addLevelName(TRACE, 'TRACE')
    logging.addLevelName(VERBOSE, 'VERBOSE')
    _logging_configured = True

    # with unit test we want pytest to add the handlers
    if unit_test:
        _logging_started = True
        return

    # Store any log messages in a buffer until we `start` function is run
    logger = logging.getLogger()
    _buff_handler = logging.handlers.BufferingHandler(1000 * 1000)
    logger.addHandler(_buff_handler)
    logger.setLevel(logging.NOTSET)

    # Add a handler that sores the last 50 debug lines to `debug_buffer` for use in crash reports
    crash_handler = logging.StreamHandler(debug_buffer)
    crash_handler.setLevel(logging.DEBUG)
    crash_handler.setFormatter(FlexGetFormatter())
    logger.addHandler(crash_handler)


def start(filename=None, level=logging.INFO, to_console=True, to_file=True):
    """After initialization, start file logging.
    """
    global _logging_started

    assert _logging_configured
    if _logging_started:
        return

    # root logger
    logger = logging.getLogger()
    level = get_level_no(level)
    logger.setLevel(level)

    formatter = FlexGetFormatter()
    if to_file:
        file_handler = logging.handlers.RotatingFileHandler(filename, maxBytes=1000 * 1024, backupCount=9)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)

    # without --cron we log to console
    if to_console:
        # Make sure we don't send any characters that the current terminal doesn't support printing
        stdout = sys.stdout
        if hasattr(stdout, 'buffer'):
            # On python 3, we need to get the buffer directly to support writing bytes
            stdout = stdout.buffer
        safe_stdout = codecs.getwriter(io_encoding)(stdout, 'replace')
        console_handler = logging.StreamHandler(safe_stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
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
