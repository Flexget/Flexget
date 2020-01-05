from argparse import SUPPRESS
from time import time

from loguru import logger
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm.query import Query
from sqlalchemy.sql.expression import ClauseElement, Executable, _literal_as_text

from flexget import manager, options
from flexget.event import event

logger = logger.bind(name='explain_sql')


class Explain(Executable, ClauseElement):
    def __init__(self, stmt):
        self.statement = _literal_as_text(stmt)


@compiles(Explain)
def explain(element, compiler, **kw):
    text = 'EXPLAIN QUERY PLAN ' + compiler.process(element.statement)
    return text


class ExplainQuery(Query):
    def __iter__(self):
        logger.info('Query:\n\t{}', str(self).replace('\n', '\n\t'))
        explain = self.session.execute(Explain(self)).fetchall()
        text = '\n\t'.join('|'.join(str(x) for x in line) for line in explain)
        before = time()
        result = Query.__iter__(self)
        logger.info('Query Time: {:0.3f} Explain Query Plan: {}', time() - before, text)
        return result


@event('manager.execute.started')
def register_sql_explain(man, options):
    if options.explain_sql:
        manager.Session.kw['query_cls'] = ExplainQuery


@event('manager.execute.completed')
def deregister_sql_explain(man, options):
    if options.explain_sql:
        manager.Session.kw.pop('query_cls', None)


@event('options.register')
def register_parser_arguments():
    options.get_parser('execute').add_argument(
        '--explain-sql', action='store_true', dest='explain_sql', default=False, help=SUPPRESS
    )
