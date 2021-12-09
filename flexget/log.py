import codecs
import collections
import contextlib
import functools
import io
import logging
import logging.handlers
import os
import sys
import threading
import uuid
import warnings
from typing import Callable, Deque, Iterator, List, Optional, Union

import colorama
import loguru
from loguru import logger

from flexget import __version__
from flexget.utils.tools import io_encoding

# A level more detailed than INFO
VERBOSE = 15
# environment variables to modify rotating log parameters from defaults of 1 MB and 9 files
ENV_MAXBYTES = 'FLEXGET_LOG_MAXBYTES'
ENV_MAXCOUNT = 'FLEXGET_LOG_MAXCOUNT'

LOG_FORMAT = (
    '<green>{time:YYYY-MM-DD HH:mm:ss}</green> <level>{level: <8}</level> '
    '<cyan>{name: <13}</cyan> <bold>{extra[task]: <15}</bold> {message}'
)

# Stores current `session_id` to keep track of originating thread for log calls
local_context = threading.local()


@contextlib.contextmanager
def capture_logs(*args, **kwargs) -> Iterator:
    """Takes the same arguments as `logger.add`, but this sync will only log messages contained in context."""
    old_id = get_log_session_id()
    session_id = local_context.session_id = old_id or str(uuid.uuid4())
    existing_filter = kwargs.pop('filter', None)
    kwargs.setdefault('format', LOG_FORMAT)

    def filter_func(record):
        if record['extra'].get('session_id') != session_id:
            return False
        if existing_filter:
            return existing_filter(record)
        return True

    kwargs['filter'] = filter_func

    log_sink = logger.add(*args, **kwargs)
    try:
        with logger.contextualize(session_id=session_id):
            yield
    finally:
        local_context.session_id = old_id
        logger.remove(log_sink)


def get_log_session_id() -> str:
    return getattr(local_context, 'session_id', None)


def record_patcher(record: 'loguru.Record') -> None:
    # If a custom name was bound to the logger, move it from extra directly into the record
    name = record['extra'].pop('name', None)
    if name:
        record['name'] = name


class InterceptHandler(logging.Handler):
    """Catch any stdlib log messages from our deps and propagate to loguru."""

    def emit(self, record: logging.LogRecord):
        # Get corresponding Loguru level if it exists
        level: Union[str, int]
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.bind(name=record.name).opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


_logging_configured = False
_startup_buffer: List['loguru.Record'] = []
_startup_buffer_id: Optional[int] = None
_logging_started = False
# Stores the last 100 debug messages
debug_buffer: Deque['loguru.Message'] = collections.deque(maxlen=100)
_log_filters = []  # Stores filter functions


def _log_filterer(record):
    """This is the function we add to our loguru handlers. It will dynamically use all filters we add later."""
    return all(f(record) for f in _log_filters)


def add_filter(func: Callable[['loguru.Record'], bool]):
    """Adds a filter function to the log handlers."""
    _log_filters.append(func)


def remove_filter(func: Callable[['loguru.Record'], bool]):
    """Removes a filter function from the log handlers."""
    _log_filters.remove(func)


def initialize(unit_test: bool = False) -> None:
    """Prepare logging."""
    # Remove default loguru sinks
    logger.remove()
    global _logging_configured, _logging_started, _buff_handler

    if _logging_configured:
        return

    if 'dev' in __version__:
        warnings.filterwarnings('always', category=DeprecationWarning, module='flexget.*')
    warnings.simplefilter('once', append=True)

    logger.level('VERBOSE', no=VERBOSE, color='<bold>', icon='👄')

    logger.__class__.verbose = functools.partialmethod(logger.__class__.log, 'VERBOSE')
    logger.configure(extra={'task': '', 'session_id': None}, patcher=record_patcher)

    _logging_configured = True

    # with unit test we want pytest to add the handlers
    if unit_test:
        _logging_started = True
        return

    # Store any log messages in a buffer until we `start` function is run
    global _startup_buffer_id
    _startup_buffer_id = logger.add(
        lambda message: _startup_buffer.append(message.record), level='DEBUG', format=LOG_FORMAT
    )

    # Add a handler that sores the last 100 debug lines to `debug_buffer` for use in crash reports
    logger.add(
        lambda message: debug_buffer.append(message),
        level='DEBUG',
        format=LOG_FORMAT,
        backtrace=True,
        diagnose=True,
    )

    std_logger = logging.getLogger()
    std_logger.addHandler(InterceptHandler())


def start(
    filename: str = None, level: str = 'INFO', to_console: bool = True, to_file: bool = True
) -> None:
    """After initialization, start file logging."""
    global _logging_started

    assert _logging_configured
    if _logging_started:
        return

    if level == 'NONE':
        return

    # Make sure stdlib logger is set so that dependency logging gets propagated
    logging.getLogger().setLevel(logger.level(level).no)

    if to_file and filename:
        logger.add(
            filename,
            level=level,
            rotation=int(os.environ.get(ENV_MAXBYTES, 1000 * 1024)),
            retention=int(os.environ.get(ENV_MAXCOUNT, 9)),
            encoding='utf-8',
            format=LOG_FORMAT,
            filter=_log_filterer,
        )

    # without --cron we log to console
    if to_console:
        if not sys.stdout:
            logger.debug("No sys.stdout, can't log to console.")
        else:
            # Make sure we don't send any characters that the current terminal doesn't support printing
            if sys.version_info >= (3, 7):
                sys.stdout.reconfigure(errors='replace')
                out = sys.stdout
            else:
                out = io.TextIOWrapper(sys.stdout.buffer, encoding=io_encoding, errors='replace')
                # Loguru only autodetects whether we need to wrap the stream only when it's sys.__stdout__
                # since we've already wrapped it we need to add the colorama support ourselves
                if os.name == "nt":
                    out = colorama.AnsiToWin32(
                        out, convert=True, strip=False, autoreset=False
                    ).stream
            logger.add(out, level=level, format=LOG_FORMAT, filter=_log_filterer)

    # flush what we have stored from the plugin initialization
    global _startup_buffer, _startup_buffer_id
    if _startup_buffer_id:
        logger.remove(_startup_buffer_id)
        for record in _startup_buffer:
            level, message = record['level'].name, record['message']
            logger.patch(lambda r: r.update(record)).log(level, message)
        _startup_buffer = []
        _startup_buffer_id = None
    _logging_started = True
