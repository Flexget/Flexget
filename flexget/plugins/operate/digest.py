import pickle
from datetime import datetime

from loguru import logger
from sqlalchemy import Column, DateTime, Integer, Unicode, select

from flexget import db_schema, plugin
from flexget.config_schema import one_or_more
from flexget.db_schema import versioned_base
from flexget.entry import Entry, EntryState
from flexget.event import event
from flexget.manager import Session
from flexget.utils import json, serialization
from flexget.utils.database import entry_synonym
from flexget.utils.sqlalchemy_utils import table_add_column, table_schema
from flexget.utils.tools import parse_timedelta

logger = logger.bind(name='digest')
Base = versioned_base('digest', 2)


@db_schema.upgrade('digest')
def upgrade(ver, session):
    if None is ver:
        ver = 0
    if ver == 0:
        table = table_schema('digest_entries', session)
        table_add_column(table, 'json', Unicode, session)
        # Make sure we get the new schema with the added column
        table = table_schema('digest_entries', session)
        for row in session.execute(select([table.c.id, table.c.entry])):
            try:
                p = pickle.loads(row['entry'])
                session.execute(
                    table.update()
                    .where(table.c.id == row['id'])
                    .values(json=json.dumps(p, encode_datetime=True))
                )
            except KeyError as e:
                logger.error('Unable error upgrading backlog pickle object due to {}', str(e))

        ver = 1
    if ver == 1:
        table = table_schema('digest_entries', session)
        for row in session.execute(select([table.c.id, table.c.json])):
            if not row['json']:
                # Seems there could be invalid data somehow. See #2590
                continue
            data = json.loads(row['json'], decode_datetime=True)
            # If title looked like a date, make sure it's a string
            title = str(data.pop('title'))
            e = Entry(title=title, **data)
            session.execute(
                table.update().where(table.c.id == row['id']).values(json=serialization.dumps(e))
            )
        ver = 2
    return ver


class DigestEntry(Base):
    __tablename__ = 'digest_entries'
    id = Column(Integer, primary_key=True)
    list = Column(Unicode, index=True)
    added = Column(DateTime, default=datetime.now)
    _json = Column('json', Unicode)
    entry = entry_synonym('_json')


class OutputDigest:
    schema = {
        'oneOf': [
            {'type': 'string'},
            {
                'type': 'object',
                'properties': {
                    'list': {'type': 'string'},
                    'state': one_or_more(
                        {'type': 'string', 'enum': ['accepted', 'rejected', 'failed', 'undecided']}
                    ),
                },
                'required': ['list'],
                'additionalProperties': False,
            },
        ]
    }

    def prepare_config(self, config):
        if not isinstance(config, dict):
            config = {'list': config}
        config.setdefault('state', ['accepted'])
        if not isinstance(config['state'], list):
            config['state'] = [config['state']]
        return config

    def on_task_learn(self, task, config):
        config = self.prepare_config(config)
        with Session() as session:
            for entry in task.all_entries:
                state = str(entry.state)
                if state not in config['state']:
                    continue
                entry['digest_task'] = task.name
                entry['digest_state'] = state
                session.add(DigestEntry(list=config['list'], entry=entry))


class FromDigest:
    schema = {
        'type': 'object',
        'properties': {
            'list': {'type': 'string'},
            'limit': {
                'deprecated': 'The `limit` option of from_digest is deprecated. Use the `limit` plugin instead.',
                'type': 'integer',
            },
            'expire': {
                'oneOf': [{'type': 'string', 'format': 'interval'}, {'type': 'boolean'}],
                'default': True,
            },
            'restore_state': {'type': 'boolean', 'default': False},
        },
        'required': ['list'],
        'additionalProperties': False,
    }

    def on_task_input(self, task, config):
        entries = []
        with Session() as session:
            digest_entries = session.query(DigestEntry).filter(DigestEntry.list == config['list'])
            # Remove any entries older than the expire time, if defined.
            if isinstance(config.get('expire'), str):
                expire_time = parse_timedelta(config['expire'])
                digest_entries.filter(DigestEntry.added < datetime.now() - expire_time).delete()
            for index, digest_entry in enumerate(
                digest_entries.order_by(DigestEntry.added.desc()).all()
            ):
                # Just remove any entries past the limit, if set.
                if 0 < config.get('limit', -1) <= index:
                    session.delete(digest_entry)
                    continue
                entry = digest_entry.entry
                if config.get('restore_state') and entry.get('digest_state'):
                    # Not sure this is the best way, but we don't want hooks running on this task
                    # (like backlog hooking entry.fail)
                    entry._state = EntryState(entry['digest_state'])
                entries.append(entry)
                # If expire is 'True', we remove it after it is output once.
                if config.get('expire', True) is True:
                    session.delete(digest_entry)
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(OutputDigest, 'digest', api_ver=2)
    plugin.register(FromDigest, 'from_digest', api_ver=2)
