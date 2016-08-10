from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

from functools import partial

import logging
from datetime import datetime

from sqlalchemy import Column, String, Integer, DateTime, Unicode, desc

from flexget import options, plugin
from flexget.event import event
from flexget.logger import console
from flexget.manager import Base, Session
from flexget.options import CLITable, table_parser, CLITableError

log = logging.getLogger('history')


class History(Base):
    __tablename__ = 'history'

    id = Column(Integer, primary_key=True)
    task = Column('feed', String)
    filename = Column(String)
    url = Column(String)
    title = Column(Unicode)
    time = Column(DateTime)
    details = Column(String)

    def __init__(self):
        self.time = datetime.now()

    def __str__(self):
        return '<History(filename=%s,task=%s)>' % (self.filename, self.task)

    def to_dict(self):
        return {
            'id': self.id,
            'task': self.task,
            'filename': self.filename,
            'url': self.url,
            'title': self.title,
            'time': self.time.isoformat(),
            'details': self.details,
        }


class PluginHistory(object):
    """Records all accepted entries for later lookup"""

    schema = {'type': 'boolean'}

    def on_task_learn(self, task, config):
        """Add accepted entries to history"""
        if config is False:
            return  # Explicitly disabled with configuration

        for entry in task.accepted:
            item = History()
            item.task = task.name
            item.filename = entry.get('output', None)
            item.title = entry['title']
            item.url = entry['url']
            reason = ''
            if 'reason' in entry:
                reason = ' (reason: %s)' % entry['reason']
            item.details = 'Accepted by %s%s' % (entry.get('accepted_by', '<unknown>'), reason)
            task.session.add(item)


def do_cli(manager, options):
    ww = partial(CLITable.word_wrap, max_length=options.max_column_width)
    with Session() as session:
        query = session.query(History)
        if options.search:
            search_term = options.search.replace(' ', '%').replace('.', '%')
            query = query.filter(History.title.like('%' + search_term + '%'))
        if options.task:
            query = query.filter(History.task.like('%' + options.task + '%'))
        query = query.order_by(desc(History.time)).limit(options.limit)
        header = ['#',' Task', 'Title', 'URL', 'Stored', 'Time', 'Details']
        table_data = [header]
        for item in reversed(query.all()):
            table_data.append(
                [item.id, item.task, ww(item.title), ww(item.url), ww(item.filename) or '', item.time.strftime("%c"), item.details])
    table = CLITable(options.table_type, table_data)
    table.table.justify_columns[0] = 'center'
    try:
        console(table.output)
    except CLITableError as e:
        console('ERROR: %s' % str(e))


@event('options.register')
def register_parser_arguments():
    parser = options.register_command('history', do_cli, help='view the history of entries that FlexGet has accepted',
                                      parents=[table_parser])
    parser.add_argument('--limit', action='store', type=int, metavar='NUM', default=50,
                        help='limit to %(metavar)s results')
    parser.add_argument('--search', action='store', metavar='TERM', help='limit to results that contain %(metavar)s')
    parser.add_argument('--task', action='store', metavar='TASK', help='limit to results in specified %(metavar)s')


@event('plugin.register')
def register_plugin():
    plugin.register(PluginHistory, 'history', builtin=True, api_ver=2)
