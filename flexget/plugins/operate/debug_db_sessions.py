import inspect
import time
from threading import Lock

import sqlalchemy
from loguru import logger

from flexget import options
from flexget.event import event
from flexget.manager import Session

logger = logger.bind(name='debug_db_sess')

open_transactions_lock = (
    Lock()
)  # multiple threads may call events, be safe by getting lock when using
open_transactions = {}


def find_caller(stack):
    """Finds info about first non-sqlalchemy call in stack"""
    for frame in stack:
        # We don't care about sqlalchemy internals
        module = inspect.getmodule(frame[0])
        if not hasattr(module, '__name__'):
            continue
        if module.__name__.startswith('sqlalchemy'):
            continue
        return (module.__name__,) + tuple(frame[2:4]) + (frame[4][0].strip(),)
    logger.warning('Transaction from unknown origin')
    return None, None, None, None


def after_begin(session, transaction, connection):
    caller_info = find_caller(inspect.stack()[1:])
    with open_transactions_lock:
        if any(info[1] is not connection.connection for info in open_transactions.values()):
            logger.warning(
                'Sessions from 2 threads! Transaction 0x{:08X} opened {} Already open one(s): {}',
                id(transaction),
                caller_info,
                open_transactions,
            )
        elif open_transactions:
            logger.debug(
                'Transaction 0x{:08X} opened {} Already open one(s): {}',
                id(transaction),
                caller_info,
                open_transactions,
            )
        else:
            logger.debug('Transaction 0x{:08X} opened {}', id(transaction), caller_info)
        # Store information about this transaction
        open_transactions[transaction] = (time.time(), connection.connection) + caller_info


def after_flush(session, flush_context):
    if session.new or session.deleted or session.dirty:
        caller_info = find_caller(inspect.stack()[1:])
        with open_transactions_lock:
            # Dirty hack to support SQLAlchemy 1.1 without breaking backwards compatibility
            # _iterate_parents was renamed to _iterate_self_and_parents in 1.1
            try:
                _iterate_parents = session.transaction._iterate_parents
            except AttributeError:
                _iterate_parents = session.transaction._iterate_self_and_parents

            tid = next(id(t) for t in _iterate_parents() if t in open_transactions)
            logger.debug(
                'Transaction 0x{:08X} writing {} new: {} deleted: {} dirty: {}',
                tid,
                caller_info,
                tuple(session.new),
                tuple(session.deleted),
                tuple(session.dirty),
            )


def after_end(session, transaction):
    caller_info = find_caller(inspect.stack()[1:])
    with open_transactions_lock:
        if transaction not in open_transactions:
            # Transaction was created but a connection was never opened for it
            return
        open_time = time.time() - open_transactions[transaction][0]
        msg = 'Transaction 0x%08X closed %s (open time %s)' % (
            id(transaction),
            caller_info,
            open_time,
        )
        if open_time > 2:
            logger.warning(msg)
        else:
            logger.debug(msg)
        del open_transactions[transaction]


@event('manager.startup')
def debug_warnings(manager):
    if manager.options.debug_db_sessions:
        sqlalchemy.event.listen(Session, 'after_begin', after_begin)
        sqlalchemy.event.listen(Session, 'after_flush', after_flush)
        sqlalchemy.event.listen(Session, 'after_transaction_end', after_end)


@event('options.register')
def register_parser_arguments():
    options.get_parser().add_argument(
        '--debug-db-sessions',
        action='store_true',
        help='debug session starts and ends, for finding problems with db locks',
    )
