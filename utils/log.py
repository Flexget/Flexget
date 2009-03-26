
# TODO: purge old entries

import logging
from manager import Session, Base
from sqlalchemy import Table, Column, Integer, String, MetaData, ForeignKey

class LogMessage(Base):
    __tablename__ = 'log_once'
    
    id = Column(Integer, primary_key=True)
    md5sum = Column(String)
    # TODO: add date

    def __init__(self, md5sum):
        self.md5sum = md5sum
    
    def __repr__(self):
        return "<LogMessage('%s')>" % (self.md5sum)

def log_once(message, log=logging.getLogger('log_once')):
    """Log message only once using given logger."""
    
    import hashlib
    hash = hashlib.md5()
    hash.update(message)
    md5sum = hash.hexdigest()
    
    session = Session()
    # abort if this has already been logged
    if session.query(LogMessage).filter_by(md5sum=md5sum).first():
        session.close()
        return

    row = LogMessage(md5sum)
    session.add(row)
    session.commit()
    
    log.info(message)