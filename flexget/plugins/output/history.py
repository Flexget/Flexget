from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
from datetime import datetime

from sqlalchemy import Column, String, Integer, DateTime, Unicode

from flexget import plugin
from flexget.event import event
from flexget.manager import Base

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


@event('plugin.register')
def register_plugin():
    plugin.register(PluginHistory, 'history', builtin=True, api_ver=2)
