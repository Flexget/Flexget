from __future__ import absolute_import, division, unicode_literals
import contextlib
import logging
import logging.handlers
import sys
import threading
import uuid
import warnings

# A level more detailed than DEBUG
TRACE = 5
# A level more detailed than INFO
VERBOSE = 15


def get_level_no(level):
    if not isinstance(level, int):
        # Python logging api is horrible. This is getting the level number, which is required on python 2.6.
        level = logging.getLevelName(level.upper())
    return level


@contextlib.contextmanager
def task_logging(task):
    """Context manager which adds task information to log messages."""
    old_task = getattr(FlexGetLogger.local, 'task', '')
    FlexGetLogger.local.task = task
    try:
        yield
    finally:
        FlexGetLogger.local.task = old_task


@contextlib.contextmanager
def session_logging(session_id=None):
    """Context manager which adds a session id to track log messages amongst threads."""
    old_id = getattr(FlexGetLogger.local, 'session_id', '')
    # If command id not given, keep using current, or create one if none already set
    FlexGetLogger.local.session_id = session_id or old_id or uuid.uuid4()
    try:
        yield FlexGetLogger.local.session_id
    finally:
        FlexGetLogger.local.session_id = old_id


def get_session_id():
    """Returns the current logging session id."""
    return getattr(FlexGetLogger.local, 'session_id', '')


class SessionFilter(logging.Filter):
    def __init__(self, session_id):
        self.session_id = session_id

    def filter(self, record):
        return getattr(record, 'session_id', None) == self.session_id


@contextlib.contextmanager
def capture_logging(stream, loglevel=None):
    """Context manager which captures all log output to given `stream` while in scope."""
    root_logger = logging.getLogger()
    streamhandler = logging.StreamHandler(stream)
    if loglevel is not None:
        loglevel = get_level_no(loglevel)
        streamhandler.setLevel(loglevel)
        # If requested loglevel is lower than the root logger is filtering for, we need to turn it down.
        # All existing handlers should have their desired level set and not be affected.
        if not root_logger.isEnabledFor(loglevel):
            root_logger.setLevel(loglevel)
    streamhandler.setFormatter(FlexGetFormatter())
    with session_logging() as session_id:
        # Filtering on this session id will make sure we don't get log messages from other threads
        streamhandler.addFilter(SessionFilter(session_id))
        root_logger.addHandler(streamhandler)
        try:
            yield
        finally:
            root_logger.removeHandler(streamhandler)


class FlexGetLogger(logging.Logger):
    """Custom logger that adds trace and verbose logging methods, and contextual information to log records."""
    local = threading.local()

    def makeRecord(self, name, level, fn, lno, msg, args, exc_info, func=None, extra=None):
        extra = extra or {}
        extra.update(
            task=getattr(self.local, 'task', ''),
            session_id=getattr(self.local, 'session_id', ''))
        # Replace newlines in log messages with \n
        msg = msg.replace('\n', '\\n')
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
        self._fmt = self.flexget_fmt if hasattr(record, 'task') else self.plain_fmt
        return super(FlexGetFormatter, self).format(record)


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
        console_handler = logging.StreamHandler(sys.stdout)
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
