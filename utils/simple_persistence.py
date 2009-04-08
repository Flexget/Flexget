import logging
from manager import Base
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, PickleType

log = logging.getLogger('util.simple_persistence')

class SimpleKeyValue(Base):
    """Declarative"""
    
    __tablename__ = 'simple_persistence'
    
    id = Column(Integer, primary_key=True)
    feed = Column(String)
    module = Column(String)
    key = Column(String)
    value = Column(PickleType)
    added = Column(DateTime, default=datetime.now())

    def __init__(self, feed, module, key, value):
        self.feed = feed
        self.key = key
        self.value = value
    
    def __repr__(self):
        return "<SimpleKeyValue('%s','%s','%s')>" % (self.feed, self.key, self.value)

class SimplePersistence(object):
    
    def __init__(self, feed):
        self.feed = feed
        
    def set(self, key, value):
        skv = SimpleKeyValue(self.feed.name, self.feed.current_module, key, value)
        self.feed.session.add(skv)
    
    def get(self, key, default=None):
        skv = self.feed.session.query(SimpleKeyValue).find(SimpleKeyValue.feed==self.feed.name).\
            find(SimpleKeyValue.module==self.feed.current_module).find(SimpleKeyValue.key==key).first()
        if not skv:
            return default
        else:
            return skv.value
        
    def setdefault(self, key, default):
        got = self.get(key)
        if not got:
            self.set(key, default)
            return default
        else:
            return got
