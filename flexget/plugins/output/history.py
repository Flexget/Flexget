from __future__ import unicode_literals, division, absolute_import
import logging
from datetime import datetime
from argparse import SUPPRESS
from sqlalchemy import Column, String, Integer, DateTime, Unicode, desc
from flexget.manager import Base, Session
from flexget.plugin import register_parser_option, register_plugin

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

    def on_process_start(self, task):
        if task.manager.options.history:
            task.manager.disable_tasks()
            session = Session()
            print '-- History: ' + '-' * 67
            for item in reversed(session.query(History).order_by(desc(History.id)).limit(50).all()):
                print ' Task    : %s' % item.task
                print ' Title   : %s' % item.title.encode('utf-8')
                print ' Url     : %s' % item.url
                if item.filename:
                    print ' Stored  : %s' % item.filename
                print ' Time    : %s' % item.time.strftime("%c")
                print ' Details : %s' % item.details
                print '-' * 79
            session.close()

    def on_task_exit(self, task):
        """Add accepted entries to history"""

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

register_plugin(PluginHistory, '--history', builtin=True)
register_parser_option('--history', action='store_true', dest='history', default=False,
                       help='List 50 latest accepted entries.')
register_parser_option('--downloads', action='store_true', dest='history', default=False,
                       help=SUPPRESS)
