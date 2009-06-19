import logging
from flexget.manager import Base
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, PickleType

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
    
    def __init__(self, feed):
        self.feed = feed
        
    def set(self, key, value):
        skv = self.feed.session.query(SimpleKeyValue).filter(SimpleKeyValue.feed==self.feed.name).\
            filter(SimpleKeyValue.plugin==self.feed.current_plugin).filter(SimpleKeyValue.key==key).first()
        if skv:
            # update existing
            skv.value = value
        else:
            # add new key
            skv = SimpleKeyValue(self.feed.name, self.feed.current_plugin, key, value)
            self.feed.session.add(skv)
    
    def get(self, key, default=None):
        skv = self.feed.session.query(SimpleKeyValue).filter(SimpleKeyValue.feed==self.feed.name).\
            filter(SimpleKeyValue.plugin==self.feed.current_plugin).filter(SimpleKeyValue.key==key).first()
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
