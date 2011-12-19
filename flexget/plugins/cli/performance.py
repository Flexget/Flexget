import logging
from optparse import SUPPRESS_HELP
from flexget.plugin import register_parser_option
from flexget.event import event

log = logging.getLogger('performance')

performance = {}

_start = {}

query_count = 0


def log_query_count(name_point):
    """Debugging purposes, allows logging number of executed queries at :name_point:"""
    log.info('At point named `%s` total of %s queries were ran' % (name_point, query_count))


@event('manager.startup')
def startup(manager):
    if manager.options.debug_perf:
        log.info('Enabling plugin and SQLAlchemy performance debugging')
        import time

        # Monkeypatch query counter for SQLAlchemy
        from sqlalchemy.engine import Connection
        if hasattr(Connection, 'execute'):
            orig_f = Connection.execute

            def monkeypatched(*args, **kwargs):
                global query_count
                query_count += 1
                return orig_f(*args, **kwargs)

            Connection.execute = monkeypatched
        else:
            log.critical('Unable to monkeypatch sqlalchemy')

        @event('feed.execute.before_plugin')
        def before(feed, keyword):
            fd = _start.setdefault(feed.name, {})
            fd.setdefault('time', {})[keyword] = time.time()
            fd.setdefault('queries', {})[keyword] = query_count

        @event('feed.execute.after_plugin')
        def after(feed, keyword):
            took = time.time() - _start[feed.name]['time'][keyword]
            queries = query_count - _start[feed.name]['queries'][keyword]
            # Store results, increases previous values
            pd = performance.setdefault(feed.name, {})
            data = pd.setdefault(keyword, {})
            data['took'] = data.get('took', 0) + took
            data['queries'] = data.get('queries', 0) + queries

        @event('manager.execute.completed')
        def results(manager):
            for name, data in performance.iteritems():
                log.info('Performance results for feed %s:' % name)
                for keyword, results in data.iteritems():
                    took = results['took']
                    queries = results['queries']
                    if took > 0.1 or queries > 10:
                        log.info('%-15s took %0.2f sec (%s queries)' % (keyword, took, queries))


register_parser_option('--debug-perf', action='store_true', dest='debug_perf', default=False,
                       help=SUPPRESS_HELP)
