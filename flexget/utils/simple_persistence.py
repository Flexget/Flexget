import logging
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, PickleType
from flexget.manager import Base, Session

log = logging.getLogger('util.simple_persistence')


class SimpleKeyValue(Base):
    """Declarative"""

    __tablename__ = 'simple_persistence'

    id = Column(Integer, primary_key=True)
    feed = Column(String)
    plugin = Column(String)
    key = Column(String)
    value = Column(PickleType)
    added = Column(DateTime, default=datetime.now())

    def __init__(self, feed, plugin, key, value):
        self.feed = feed
        self.plugin = plugin
        self.key = key
        self.value = value

    def __repr__(self):
        return "<SimpleKeyValue('%s','%s','%s')>" % (self.feed, self.key, self.value)


class SimplePersistence(object):

    def __init__(self, plugin, session=None):
        self.feedname = None
        self.plugin = plugin
        self.session = session

    def set(self, key, value):
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

    def get(self, key, default=None):
        session = self.session or Session()
        skv = session.query(SimpleKeyValue).filter(SimpleKeyValue.feed == self.feedname).\
            filter(SimpleKeyValue.plugin == self.plugin).filter(SimpleKeyValue.key == key).first()
        if not self.session:
            session.close()
        if not skv:
            return default
        else:
            return skv.value

    def setdefault(self, key, default):
        empty = object()
        got = self.get(key, empty)
        if got is empty:
            log.debug('storing default for %s' % key)
            self.set(key, default)
            return default
        else:
            return got


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
