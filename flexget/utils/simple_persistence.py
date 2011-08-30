"""
NOTE:

Avoid using this module on your own or in plugins, this was originally made for 0.9 -> 1.0 transition.

You can safely use feed.simple_persistence and manager.persist, if we implement something better we
can replace underlying mechanism in single point (and provide transparent switch).
"""

import logging
from datetime import datetime
import pickle
from sqlalchemy import Column, Integer, String, DateTime, PickleType, select
from UserDict import DictMixin
from flexget import schema
from flexget.manager import Session
from flexget.utils.database import safe_pickle_synonym
from flexget.utils.sqlalchemy_utils import table_schema

log = logging.getLogger('util.simple_persistence')
Base = schema.versioned_base('simple_persistence', 1)


@schema.upgrade('simple_persistence')
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
            except Exception, e:
                log.warning('Couldn\'t load %s:%s removing from db: %s' % (row['plugin'], row['key'], e))
                session.execute(table.delete().where(table.c.id == row['id']))
        ver = 1
    return ver


class SimpleKeyValue(Base):
    """Declarative"""

    __tablename__ = 'simple_persistence'

    id = Column(Integer, primary_key=True)
    feed = Column(String)
    plugin = Column(String)
    key = Column(String)
    _value = Column('value', PickleType)
    value = safe_pickle_synonym('_value')
    added = Column(DateTime, default=datetime.now())

    def __init__(self, feed, plugin, key, value):
        self.feed = feed
        self.plugin = plugin
        self.key = key
        self.value = value

    def __repr__(self):
        return "<SimpleKeyValue('%s','%s','%s')>" % (self.feed, self.key, self.value)


class SimplePersistence(DictMixin):

    def __init__(self, plugin, session=None):
        self.feedname = None
        self.plugin = plugin
        self.session = session

    def __setitem__(self, key, value):
        session = self.session or Session()
        skv = session.query(SimpleKeyValue).filter(SimpleKeyValue.feed == self.feedname).\
                filter(SimpleKeyValue.plugin == self.plugin).filter(SimpleKeyValue.key == key).first()
        if skv:
            # update existing
            log.debug('updating key %s value %s' % (key, repr(value)))
            skv.value = value
        else:
            # add new key
            skv = SimpleKeyValue(self.feedname, self.plugin, key, value)
            log.debug('adding key %s value %s' % (key, repr(value)))
            session.add(skv)
        if not self.session:
            # If we created a temporary session for this call, make sure we commit
            session.commit()
            session.close()

    def __getitem__(self, key):
        session = self.session or Session()
        skv = session.query(SimpleKeyValue).filter(SimpleKeyValue.feed == self.feedname).\
            filter(SimpleKeyValue.plugin == self.plugin).filter(SimpleKeyValue.key == key).first()
        if not self.session:
            session.close()
        if not skv:
            raise KeyError('%s is not contained in the simple_persistence table.' % key)
        else:
            return skv.value

    def __delitem__(self, key):
        session = self.session or Session()
        session.query(SimpleKeyValue).filter(SimpleKeyValue.feed == self.feedname).\
            filter(SimpleKeyValue.plugin == self.plugin).filter(SimpleKeyValue.key == key).delete()
        if not self.session:
            session.commit()
            session.close()

    def keys(self):
        session = self.session or Session()
        query = session.query(SimpleKeyValue.key).filter(SimpleKeyValue.feed == self.feedname).\
             filter(SimpleKeyValue.plugin == self.plugin).all()
        if query:
            return [item.key for item in query]
        else:
            return []


class SimpleFeedPersistence(SimplePersistence):

    def __init__(self, feed):
        self.feed = feed

    @property
    def plugin(self):
        return self.feed.current_plugin

    @property
    def feedname(self):
        return self.feed.name

    @property
    def session(self):
        return self.feed.session
