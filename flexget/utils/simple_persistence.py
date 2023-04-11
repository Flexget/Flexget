"""
NOTE:

Avoid using this module on your own or in plugins, this was originally made for 0.9 -> 1.0 transition.

You can safely use task.simple_persistence and manager.persist, if we implement something better we
can replace underlying mechanism in single point (and provide transparent switch).
"""
import pickle
from collections import defaultdict
from collections.abc import MutableMapping
from datetime import datetime

from loguru import logger
from sqlalchemy import Column, DateTime, Index, Integer, String, Unicode, select

from flexget import db_schema
from flexget.event import event
from flexget.manager import Session
from flexget.utils import json
from flexget.utils.database import json_synonym
from flexget.utils.sqlalchemy_utils import create_index, table_add_column, table_schema

logger = logger.bind(name='util.simple_persistence')
Base = db_schema.versioned_base('simple_persistence', 4)

# Used to signify that a given key should be deleted from simple persistence on flush
DELETE = object()


@db_schema.upgrade('simple_persistence')
def upgrade(ver, session):
    if ver is None:
        # Upgrade to version 0 was a failed attempt at cleaning bad entries from our table, better attempt in ver 1
        ver = 0
    if ver == 0:
        try:
            # Remove any values that are not loadable.
            table = table_schema('simple_persistence', session)
            for row in session.execute(
                select([table.c.id, table.c.plugin, table.c.key, table.c.value])
            ):
                try:
                    pickle.loads(row['value'])
                except Exception as e:
                    logger.warning(
                        "Couldn't load {}:{} removing from db: {}", row['plugin'], row['key'], e
                    )
                    session.execute(table.delete().where(table.c.id == row['id']))
        except Exception as e:
            logger.warning(
                "Couldn't upgrade the simple_persistence table. Commencing nuke. Error: {}", e
            )
            raise db_schema.UpgradeImpossible
        ver = 1
    if ver == 1:
        logger.info('Creating index on simple_persistence table.')
        create_index('simple_persistence', session, 'feed', 'plugin', 'key')
        ver = 2
    if ver == 2 or ver == 3:
        table = table_schema('simple_persistence', session)
        table_add_column(table, 'json', Unicode, session)
        # Make sure we get the new schema with the added column
        table = table_schema('simple_persistence', session)
        failures = 0
        for row in session.execute(select([table.c.id, table.c.value])):
            try:
                p = pickle.loads(row['value'])
                session.execute(
                    table.update()
                    .where(table.c.id == row['id'])
                    .values(json=json.dumps(p, encode_datetime=True))
                )
            except Exception:
                failures += 1
        if failures > 0:
            logger.error(
                'Error upgrading {} simple_persistence pickle objects. Some information has been lost.',
                failures,
            )
        ver = 4
    return ver


@event('manager.db_cleanup')
def db_cleanup(manager, session):
    """Clean up values in the db from tasks which no longer exist."""
    # SKVs not associated with any task use None as task tame
    existing_tasks = [*list(manager.tasks), None]
    session.query(SimpleKeyValue).filter(~SimpleKeyValue.task.in_(existing_tasks)).delete(
        synchronize_session=False
    )


class SimpleKeyValue(Base):
    __tablename__ = 'simple_persistence'

    id = Column(Integer, primary_key=True)
    task = Column('feed', String)
    plugin = Column(String)
    key = Column(String)
    _json = Column('json', Unicode)
    value = json_synonym('_json')
    added = Column(DateTime, default=datetime.now())

    def __init__(self, task, plugin, key, value):
        self.task = task
        self.plugin = plugin
        self.key = key
        self.value = value

    def __repr__(self):
        return f"<SimpleKeyValue('{self.task}','{self.key}','{self.value}')>"


Index(
    'ix_simple_persistence_feed_plugin_key',
    SimpleKeyValue.task,
    SimpleKeyValue.plugin,
    SimpleKeyValue.key,
)


class SimplePersistence(MutableMapping):
    """
    Store simple values that need to be persisted between FlexGet runs. Interface is like a `dict`.

    This should only be used if a plugin needs to store a few values, otherwise it should create a full table in
    the database.
    """

    # Stores values in store[taskname][pluginname][key] format
    class_store = defaultdict(lambda: defaultdict(dict))

    def __init__(self, plugin=None):
        self.taskname = None
        self.plugin = plugin

    @property
    def store(self):
        return self.class_store[self.taskname][self.plugin]

    def __setitem__(self, key, value):
        logger.debug('setting key {} value {}', key, repr(value))
        self.store[key] = value

    def __getitem__(self, key):
        if key not in self.store or self.store[key] == DELETE:
            raise KeyError('%s is not contained in the simple_persistence table.' % key)
        return self.store[key]

    def __delitem__(self, key):
        self.store[key] = DELETE

    def __iter__(self):
        return iter(self.store)

    def __len__(self):
        return len(self.store)

    @classmethod
    def load(cls, task=None):
        """Load all key/values from `task` into memory from database."""
        with Session() as session:
            for skv in session.query(SimpleKeyValue).filter(SimpleKeyValue.task == task).all():
                try:
                    cls.class_store[task][skv.plugin][skv.key] = skv.value
                except TypeError as e:
                    logger.warning(
                        'Value stored in simple_persistence cannot be decoded. It will be removed. Error: {}',
                        str(e),
                    )
                    cls.class_store[task][skv.plugin][skv.key] = DELETE

    @classmethod
    def flush(cls, task=None):
        """Flush all in memory key/values to database."""
        logger.debug('Flushing simple persistence for task {} to db.', task)
        with Session() as session:
            for pluginname in cls.class_store[task]:
                for key, value in cls.class_store[task][pluginname].items():
                    query = (
                        session.query(SimpleKeyValue)
                        .filter(SimpleKeyValue.task == task)
                        .filter(SimpleKeyValue.plugin == pluginname)
                        .filter(SimpleKeyValue.key == key)
                    )
                    if value == DELETE:
                        query.delete()
                    else:
                        updated = query.update(
                            {'value': json.dumps(value, encode_datetime=True)},
                            synchronize_session=False,
                        )
                        if not updated:
                            session.add(SimpleKeyValue(task, pluginname, key, value))


class SimpleTaskPersistence(SimplePersistence):
    def __init__(self, task):
        self.task = task
        self.taskname = task.name

    @property
    def plugin(self):
        return self.task.current_plugin


@event('manager.startup')
def load_taskless(manager):
    """Loads all key/value pairs into memory which aren't associated with a specific task."""
    SimplePersistence.load()


@event('manager.shutdown')
def flush_taskless(manager):
    SimplePersistence.flush()


@event('task.execute.started')
def load_task(task):
    """Loads all key/value pairs into memory before a task starts."""
    if not SimplePersistence.class_store[task.name]:
        SimplePersistence.load(task.name)


@event('task.execute.completed')
def flush_task(task):
    """Stores all in memory key/value pairs to database when a task has completed."""
    SimplePersistence.flush(task.name)
    # In daemon mode, we don't want to wait until shutdown to flush taskless
    if task.manager.is_daemon:
        SimplePersistence.flush()
