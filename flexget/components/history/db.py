from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import Column, DateTime, Integer, String, Unicode

from flexget.event import event
from flexget.manager import Base

logger = logger.bind(name='history.db')


class History(Base):
    __tablename__ = 'history'

    id = Column(Integer, primary_key=True)
    task = Column('feed', String)
    filename = Column(String)
    url = Column(String)
    title = Column(Unicode)
    time = Column(DateTime)
    details = Column(String)

    def __init__(self):
        self.time = datetime.now()

    def __str__(self):
        return '<History(filename=%s,task=%s)>' % (self.filename, self.task)

    def to_dict(self):
        return {
            'id': self.id,
            'task': self.task,
            'filename': self.filename,
            'url': self.url,
            'title': self.title,
            'time': self.time.isoformat(),
            'details': self.details,
        }


@event('manager.db_cleanup')
def db_cleanup(manager, session):
    # Purge task executions older than 1 year
    result = (
        session.query(History).filter(History.time < datetime.now() - timedelta(days=365)).delete()
    )
    if result:
        logger.verbose('Removed {} accepted entries from history older than 1 year', result)
