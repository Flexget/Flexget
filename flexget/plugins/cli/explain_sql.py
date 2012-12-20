from __future__ import unicode_literals, division, absolute_import
import logging
from time import time
from argparse import SUPPRESS
from sqlalchemy.orm.query import Query
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import Executable, ClauseElement, _literal_as_text
from flexget import manager
from flexget.plugin import register_parser_option
from flexget.event import event

log = logging.getLogger('explain_sql')


class Explain(Executable, ClauseElement):

    def __init__(self, stmt):
        self.statement = _literal_as_text(stmt)


@compiles(Explain)
def explain(element, compiler, **kw):
    text = 'EXPLAIN QUERY PLAN ' + compiler.process(element.statement)
    return text


class ExplainQuery(Query):

    def __iter__(self):
        log.info('Query:\n\t%s' % unicode(self).replace('\n', '\n\t'))
        explain = self.session.execute(Explain(self)).fetchall()
        text = '\n\t'.join('|'.join(str(x) for x in line) for line in explain)
        before = time()
        result = Query.__iter__(self)
        log.info('Query Time: %0.3f Explain Query Plan:\n\t%s' % (time() - before, text))
        return result


@event('manager.execute.started')
def register_sql_explain(man):
    if man.options.explain_sql:
        maininit = manager.Session.__init__

        def init(*args, **kwargs):
            kwargs['query_cls'] = ExplainQuery
            return maininit(*args, **kwargs)

        manager.Session.__init__ = init


@event('manager.execute.completed')
def deregister_sql_explain(man):
    if man.options.explain_sql:
        manager.Session = sessionmaker()


register_parser_option('--explain-sql', action='store_true', dest='explain_sql', default=False,
                       help=SUPPRESS)
