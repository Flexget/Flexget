import codecs
import collections
import contextlib
import logging
import logging.handlers
import os
import sys
import threading
import uuid
import warnings

from loguru import logger

from flexget import __version__
from flexget.utils.tools import io_encoding

# A level more detailed than DEBUG
TRACE = 5
# A level more detailed than INFO
VERBOSE = 15
# environment variables to modify rotating log parameters from defaults of 1 MB and 9 files
ENV_MAXBYTES = 'FLEXGET_LOG_MAXBYTES'
ENV_MAXCOUNT = 'FLEXGET_LOG_MAXCOUNT'

LOG_FORMAT = '<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> <level>{level: <8}</level> <cyan>{extra[name]: <13}</cyan> {extra[task]: <15} <level>{message}</level>'

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
        with logger.contextualize(task=task):
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
            session_id=getattr(local_context, 'session_id', ''),
        )
        # Replace newlines in log messages with \n
        if isinstance(msg, str):
            msg = msg.replace('\n', '\\n')

        return logging.Logger.makeRecord(
            self, name, level, fn, lno, msg, args, exc_info, func, extra, *exargs
        )

    def trace(self, msg, *args, **kwargs):
        """Log at TRACE level (more detailed than DEBUG)."""
        self.log(TRACE, msg, *args, **kwargs)

    def verbose(self, msg, *args, **kwargs):
        """Log at VERBOSE level (displayed when FlexGet is run interactively.)"""
        self.log(VERBOSE, msg, *args, **kwargs)


def record_patcher(record):
    if 'name' not in record['extra']:
        name = record['name']
        if name.startswith('flexget'):
            name = name.split('.')[-1]
        record['extra']['name'] = name


class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.bind(name=record.name).opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


_logging_configured = False
_startup_buffer = []
_startup_buffer_id = None
_logging_started = False
# Stores the last 50 debug messages
debug_buffer = RollingBuffer(maxlen=50)


def log_saver(message):
    _startup_buffer.append(message.record)


def initialize(unit_test=False):
    """Prepare logging.
    """
    logger.remove()
    global _logging_configured, _logging_started, _buff_handler

    if _logging_configured:
        return

    if 'dev' in __version__:
        warnings.filterwarnings('always', category=DeprecationWarning, module='flexget.*')
    warnings.simplefilter('once', append=True)
    logging.addLevelName(TRACE, 'TRACE')
    logging.addLevelName(VERBOSE, 'VERBOSE')

    logger.level('VERBOSE', no=VERBOSE, color='<bold>', icon='👄')

    def verbose(_, message, *args, **kwargs):
        logger.opt(depth=1).log('verbose', message, *args, **kwargs)

    logger.__class__.verbose = verbose
    logger.configure(extra={'task': '', 'session_id': None}, patcher=record_patcher)

    _logging_configured = True

    # with unit test we want pytest to add the handlers
    if unit_test:
        _logging_started = True
        return

    # Store any log messages in a buffer until we `start` function is run
    global _startup_buffer_id
    _startup_buffer_id = logger.add(log_saver, level='DEBUG', format=LOG_FORMAT)

    # Add a handler that sores the last 50 debug lines to `debug_buffer` for use in crash reports
    logger.add(debug_buffer, level='DEBUG', format=LOG_FORMAT)

    std_logger = logging.getLogger()
    std_logger.addHandler(InterceptHandler())


def start(filename=None, level=logging.INFO, to_console=True, to_file=True):
    """After initialization, start file logging.
    """
    global _logging_started

    assert _logging_configured
    if _logging_started:
        return

    # root logger
    std_logger = logging.getLogger()
    level = get_level_no(level)
    std_logger.setLevel(level)

    if to_file:
        logger.add(
            filename,
            rotation=int(os.environ.get(ENV_MAXBYTES, 1000 * 1024)),
            retention=int(os.environ.get(ENV_MAXCOUNT, 9)),
            encoding='utf-8',
            format=LOG_FORMAT,
        )

    # without --cron we log to console
    if to_console:
        # Make sure we don't send any characters that the current terminal doesn't support printing
        safe_stdout = codecs.getwriter(io_encoding)(sys.stdout.buffer, 'replace')
        logger.add(safe_stdout, format=LOG_FORMAT, colorize=True)

    # flush what we have stored from the plugin initialization
    global _startup_buffer, _startup_buffer_id
    if _startup_buffer_id:
        for record in _startup_buffer:
            level, message = record['level'], record['message']
            logger.patch(lambda r: r.update(record)).log(level, message)
        logger.remove(_startup_buffer_id)
        _startup_buffer = []
        _startup_buffer_id = None
    _logging_started = True


# Set our custom logger class as default
logging.setLoggerClass(FlexGetLogger)
