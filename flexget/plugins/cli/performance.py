from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
import logging
import time

from argparse import SUPPRESS

from flexget import options
from flexget.event import event, add_event_handler, remove_event_handler

from sqlalchemy.engine import Connection

log = logging.getLogger('performance')

performance = {}

_start = {}

query_count = 0
orig_execute = None


def log_query_count(name_point):
    """Debugging purposes, allows logging number of executed queries at :name_point:"""
    log.info('At point named `%s` total of %s queries were ran' % (name_point, query_count))


def before_plugin(task, keyword):
    fd = _start.setdefault(task.name, {})
    fd.setdefault('time', {})[keyword] = time.time()
    fd.setdefault('queries', {})[keyword] = query_count


def after_plugin(task, keyword):
    took = time.time() - _start[task.name]['time'][keyword]
    queries = query_count - _start[task.name]['queries'][keyword]
    # Store results, increases previous values
    pd = performance.setdefault(task.name, {})
    data = pd.setdefault(keyword, {})
    data['took'] = data.get('took', 0) + took
    data['queries'] = data.get('queries', 0) + queries


@event('manager.execute.started')
def startup(manager, options):
    if not options.debug_perf:
        return

    log.info('Enabling plugin and SQLAlchemy performance debugging')
    global query_count, orig_execute
    query_count = 0

    # Monkeypatch query counter for SQLAlchemy
    if hasattr(Connection, 'execute'):
        orig_execute = Connection.execute

        def monkeypatched(*args, **kwargs):
            global query_count
            query_count += 1
            return orig_execute(*args, **kwargs)

        Connection.execute = monkeypatched
    else:
        log.critical('Unable to monkeypatch sqlalchemy')

    add_event_handler('task.execute.before_plugin', before_plugin)
    add_event_handler('task.execute.after_plugin', after_plugin)


@event('manager.execute.completed')
def cleanup(manager, options):
    if not options.debug_perf:
        return

    # Print summary
    for name, data in performance.items():
        log.info('Performance results for task %s:' % name)
        for keyword, results in data.items():
            took = results['took']
            queries = results['queries']
            if took > 0.1 or queries > 10:
                log.info('%-15s took %0.2f sec (%s queries)' % (keyword, took, queries))

    # Deregister our hooks
    if hasattr(Connection, 'execute') and orig_execute:
        Connection.execute = orig_execute
    remove_event_handler('task.execute.before_plugin', before_plugin)
    remove_event_handler('task.execute.after_plugin', after_plugin)


@event('options.register')
def register_parser_arguments():
    options.get_parser('execute').add_argument(
        '--debug-perf', action='store_true', dest='debug_perf', default=False, help=SUPPRESS
    )
