from __future__ import unicode_literals, division, absolute_import
import logging
from datetime import datetime

from sqlalchemy import Column, Unicode, PickleType, Integer, DateTime

from flexget import plugin
from flexget.db_schema import versioned_base
from flexget.entry import Entry
from flexget.event import event
from flexget.manager import Session
from flexget.utils.database import safe_pickle_synonym

log = logging.getLogger('digest')
Base = versioned_base('digest', 0)


class DigestEntry(Base):
    __tablename__ = 'digest_entries'
    id = Column(Integer, primary_key=True)
    list = Column(Unicode, index=True)
    added = Column(DateTime, default=datetime.now)
    _entry = Column('entry', PickleType)
    entry = safe_pickle_synonym('_entry')


class OutputDigest(object):
    schema = {'type': 'string'}

    def on_task_learn(self, task, config):
        # TODO: Configurable entry state?
        with Session() as session:
            for entry in task.accepted:
                session.add(DigestEntry(list=config, entry=entry))


class EmitDigest(object):
    schema = {
        'type': 'object',
        'properties': {
            'list': {'type': 'string'},
            'max_entries': {'type': 'integer', 'default': -1},
            'expire_time': {'type': 'string', 'format': 'interval', 'default': '0 minutes'}
        },
        'required': ['list'],
        'additionalProperties': False
    }

    def on_task_input(self, task, config):
        entries = []
        with Session() as session:
            # TODO: order by date added, limit number, expire
            for digest_entry in session.query(DigestEntry).filter(DigestEntry.list == config['list']).all():
                entries.append(Entry(digest_entry.entry))
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(OutputDigest, 'digest', api_ver=2)
    plugin.register(EmitDigest, 'emit_digest', api_ver=2)
