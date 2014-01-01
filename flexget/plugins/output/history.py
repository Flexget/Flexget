from __future__ import unicode_literals, division, absolute_import
import logging
from datetime import datetime

from sqlalchemy import Column, String, Integer, DateTime, Unicode, desc

from flexget import options, plugin
from flexget.event import event
from flexget.manager import Base, Session
from flexget.utils.tools import console

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


class PluginHistory(object):
    """Records all accepted entries for later lookup"""

    schema = {'type': 'boolean'}

    def on_task_exit(self, task, config):
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
    session = Session()
    try:
        console('-- History: ' + '-' * 67)
        query = session.query(History)
        if options.search:
            search_term = options.search.replace(' ', '%').replace('.', '%')
            query = query.filter(History.title.like('%' + search_term + '%'))
        query = query.order_by(desc(History.time)).limit(options.limit)
        for item in reversed(query.all()):
            console(' Task    : %s' % item.task)
            console(' Title   : %s' % item.title)
            console(' Url     : %s' % item.url)
            if item.filename:
                console(' Stored  : %s' % item.filename)
            console(' Time    : %s' % item.time.strftime("%c"))
            console(' Details : %s' % item.details)
            console('-' * 79)
    finally:
        session.close()


@event('options.register')
def register_parser_arguments():
    parser = options.register_command('history', do_cli, help='view the history of entries that FlexGet has accepted')
    parser.add_argument('--limit', action='store', type=int, metavar='NUM', default=50,
                        help='limit to %(metavar)s results')
    parser.add_argument('--search', action='store', metavar='TERM', help='limit to results that contain %(metavar)s')


@event('plugin.register')
def register_plugin():
    plugin.register(PluginHistory, 'history', builtin=True, api_ver=2)
