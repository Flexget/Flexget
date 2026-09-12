from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy.orm import Mapped, mapped_column

from flexget.event import event
from flexget.manager import Base

logger = logger.bind(name='history.db')


class History(Base):
    __tablename__ = 'history'

    id: Mapped[int] = mapped_column(primary_key=True)
    task: Mapped[str | None] = mapped_column('feed')
    filename: Mapped[str | None]
    url: Mapped[str | None]
    title: Mapped[str | None]
    time: Mapped[datetime | None] = mapped_column(default=datetime.now)
    details: Mapped[str | None]

    def __str__(self):
        return f'<History(filename={self.filename},task={self.task})>'

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
