from __future__ import unicode_literals, division, absolute_import
import inspect
import logging
from threading import Lock
import time

import sqlalchemy

from flexget import options
from flexget.event import event
from flexget.manager import Session

log = logging.getLogger('debug_db_sess')

open_transactions_lock = Lock()  # multiple threads may call events, be safe by getting lock when using
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
    log.warning('session started/ended for unknown origin')
    return None, None, None, None


def after_begin(session, transaction, connection):
    caller_info = find_caller(inspect.stack()[1:])
    with open_transactions_lock:
        if open_transactions:
            log.warning('session 0x%08X %s used with already open one(s) %s',
                        id(transaction), caller_info, open_transactions)
        else:
            log.debug('session connection 0x%08X opened %s', id(transaction), caller_info)
        # Store information about this transaction
        open_transactions[transaction] = (time.time(),) + caller_info


def after_end(session, transaction):
    caller_info = find_caller(inspect.stack()[1:])
    with open_transactions_lock:
        if transaction not in open_transactions:
            # Transaction was created but a connection was never opened for it
            return
        open_time = time.time() - open_transactions[transaction][0]
        msg = 'session connection 0x%08X closed %s (open time %s)' % (id(transaction), caller_info, open_time)
        log.warning(msg) if open_time > 5 else log.debug(msg)
        del open_transactions[transaction]


@event('manager.startup')
def debug_warnings(manager):
    if manager.options.debug_db_sessions:
        sqlalchemy.event.listen(Session, 'after_begin', after_begin)
        sqlalchemy.event.listen(Session, 'after_transaction_end', after_end)


@event('options.register')
def register_parser_arguments():
    options.get_parser().add_argument('--debug-db-sessions', action='store_true',
                                      help='debug session starts and ends, for finding problems with db locks')
