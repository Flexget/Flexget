"""
NOTE:

Avoid using this module on your own or in plugins, this was originally made for 0.9 -> 1.0 transition.

You can safely use task.simple_persistence and manager.persist, if we implement something better we
can replace underlying mechanism in single point (and provide transparent switch).
"""

from __future__ import unicode_literals, division, absolute_import
import logging
from datetime import datetime
import pickle
from sqlalchemy import Column, Integer, String, DateTime, PickleType, select, Index
from UserDict import DictMixin
from flexget import db_schema
from flexget.manager import Session
from flexget.utils.database import safe_pickle_synonym
from flexget.utils.sqlalchemy_utils import table_schema, create_index

log = logging.getLogger('util.simple_persistence')
Base = db_schema.versioned_base('simple_persistence', 2)


@db_schema.upgrade('simple_persistence')
def upgrade(ver, session):
    if ver is None:
        # Upgrade to version 0 was a failed attempt at cleaning bad entries from our table, better attempt in ver 1
        ver = 0
    if ver == 0:
        # Remove any values that are not loadable.
        table = table_schema('simple_persistence', session)
        for row in session.execute(select([table.c.id, table.c.plugin, table.c.key, table.c.value])):
            try:
                p = pickle.loads(row['value'])
            except Exception as e:
                log.warning('Couldn\'t load %s:%s removing from db: %s' % (row['plugin'], row['key'], e))
                session.execute(table.delete().where(table.c.id == row['id']))
        ver = 1
    if ver == 1:
        log.info('Creating index on simple_persistence table.')
        create_index('simple_persistence', session, 'feed', 'plugin', 'key')
        ver = 2
    return ver


class SimpleKeyValue(Base):
    """Declarative"""

    __tablename__ = 'simple_persistence'

    id = Column(Integer, primary_key=True)
    task = Column('feed', String)
    plugin = Column(String)
    key = Column(String)
    _value = Column('value', PickleType)
    value = safe_pickle_synonym('_value')
    added = Column(DateTime, default=datetime.now())

    def __init__(self, task, plugin, key, value):
        self.task = task
        self.plugin = plugin
        self.key = key
        self.value = value

    def __repr__(self):
        return "<SimpleKeyValue('%s','%s','%s')>" % (self.task, self.key, self.value)

Index('ix_simple_persistence_feed_plugin_key', SimpleKeyValue.task, SimpleKeyValue.plugin, SimpleKeyValue.key)


class SimplePersistence(DictMixin):

    def __init__(self, plugin, session=None):
        self.taskname = None
        self.plugin = plugin
        self.session = session

    def __setitem__(self, key, value):
        session = self.session or Session()
        skv = session.query(SimpleKeyValue).filter(SimpleKeyValue.task == self.taskname).\
            filter(SimpleKeyValue.plugin == self.plugin).filter(SimpleKeyValue.key == key).first()
        if skv:
            # update existing
            log.debug('updating key %s value %s' % (key, repr(value)))
            skv.value = value
        else:
            # add new key
            skv = SimpleKeyValue(self.taskname, self.plugin, key, value)
            log.debug('adding key %s value %s' % (key, repr(value)))
            session.add(skv)
        if not self.session:
            # If we created a temporary session for this call, make sure we commit
            session.commit()
            session.close()

    def __getitem__(self, key):
        session = self.session or Session()
        skv = session.query(SimpleKeyValue).filter(SimpleKeyValue.task == self.taskname).\
            filter(SimpleKeyValue.plugin == self.plugin).filter(SimpleKeyValue.key == key).first()
        if not self.session:
            session.close()
        if not skv:
            raise KeyError('%s is not contained in the simple_persistence table.' % key)
        else:
            return skv.value

    def __delitem__(self, key):
        session = self.session or Session()
        session.query(SimpleKeyValue).filter(SimpleKeyValue.task == self.taskname).\
            filter(SimpleKeyValue.plugin == self.plugin).filter(SimpleKeyValue.key == key).delete()
        if not self.session:
            session.commit()
            session.close()

    def keys(self):
        session = self.session or Session()
        query = session.query(SimpleKeyValue.key).filter(SimpleKeyValue.task == self.taskname).\
            filter(SimpleKeyValue.plugin == self.plugin).all()
        if query:
            return [item.key for item in query]
        else:
            return []


class SimpleTaskPersistence(SimplePersistence):

    def __init__(self, task):
        self.task = task

    @property
    def plugin(self):
        return self.task.current_plugin

    @property
    def taskname(self):
        return self.task.name

    @property
    def session(self):
        return self.task.session
