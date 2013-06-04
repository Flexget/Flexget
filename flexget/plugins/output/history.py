from __future__ import unicode_literals, division, absolute_import
import logging
from datetime import datetime
from argparse import SUPPRESS

from sqlalchemy import Column, String, Integer, DateTime, Unicode, desc

from flexget.manager import Base, Session
from flexget.plugin import register_parser_option, register_plugin, PluginError
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
    """
    Provides --history
    """

    schema = {'type': 'boolean'}

    def on_process_start(self, task, config):
        if task.manager.options.history:
            try:
                count = int(task.manager.options.history)
            except ValueError:
                task.manager.disable_tasks()
                raise PluginError('Invalid --history value')
            task.manager.disable_tasks()
            session = Session()
            console('-- History: ' + '-' * 67)
            for item in reversed(session.query(History).order_by(desc(History.id)).limit(count).all()):
                console(' Task    : %s' % item.task)
                console(' Title   : %s' % item.title)
                console(' Url     : %s' % item.url)
                if item.filename:
                    console(' Stored  : %s' % item.filename)
                console(' Time    : %s' % item.time.strftime("%c"))
                console(' Details : %s' % item.details)
                console('-' * 79)
            session.close()

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


register_plugin(PluginHistory, 'history', builtin=True, api_ver=2)
register_parser_option('--history', action='store', nargs='?', dest='history', const=50,
                       help='List latest accepted entries. Default: 50')
register_parser_option('--downloads', action='store_true', dest='history', default=False,
                       help=SUPPRESS)
