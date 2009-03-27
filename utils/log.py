"""Logging utilities"""

import logging
from manager import Session, Base
from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, DateTime

log = logging.getLogger('util.log')

class LogMessage(Base):
    """Declarative"""
    
    __tablename__ = 'log_once'
    
    id = Column(Integer, primary_key=True)
    md5sum = Column(String)
    added = Column(DateTime)

    def __init__(self, md5sum):
        self.md5sum = md5sum
        self.added = datetime.now()
    
    def __repr__(self):
        return "<LogMessage('%s')>" % (self.md5sum)
    
def purge():
    """Purge old messages from database"""
    old = datetime.now() - timedelta(days=365)
    session = Session()
    for message in session.query(LogMessage).filter(LogMessage.added < old):
        log.debug('purging: %s' % message)
        session.delete(message)
    session.commit()

def log_once(message, logger=logging.getLogger('log_once')):
    """Log message only once using given logger."""
    purge()
    
    import hashlib
    digest = hashlib.md5()
    digest.update(message)
    md5sum = digest.hexdigest()
    
    session = Session()
    # abort if this has already been logged
    if session.query(LogMessage).filter_by(md5sum=md5sum).first():
        session.close()
        return

    row = LogMessage(md5sum)
    session.add(row)
    session.commit()
    
    logger.info(message)