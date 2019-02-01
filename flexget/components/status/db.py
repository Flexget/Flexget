from __future__ import unicode_literals, division, absolute_import
import logging
import datetime
from datetime import timedelta

from flexget.utils.database import with_session
from flexget.utils.sqlalchemy_utils import create_index
from sqlalchemy import Column, Integer, String, DateTime, Boolean, select, func, Index
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.schema import ForeignKey
from sqlalchemy.orm import relation

from flexget import db_schema
from flexget.event import event

log = logging.getLogger('status.db')
Base = db_schema.versioned_base('status', 2)


@db_schema.upgrade('status')
def upgrade(ver, session):
    if ver < 2:
        # Creates the executions table index
        create_index('status_execution', session, 'task_id', 'start', 'end', 'succeeded')
        ver = 2
    return ver


class StatusTask(Base):
    __tablename__ = 'status_task'
    id = Column(Integer, primary_key=True)
    name = Column('task', String)
    executions = relation(
        'TaskExecution', backref='task', cascade='all, delete, delete-orphan', lazy='dynamic'
    )

    def __repr__(self):
        return '<StatusTask(id=%s,name=%s)>' % (self.id, self.name)

    @hybrid_property
    def last_execution_time(self):
        if self.executions.count() == 0:
            return None
        return max(execution.start for execution in self.executions)

    @last_execution_time.expression
    def last_execution_time(cls):
        return (
            select([func.max(TaskExecution.start)])
            .where(TaskExecution.task_id == cls.id)
            .correlate(StatusTask.__table__)
            .label('last_execution_time')
        )

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'last_execution_time': self.last_execution_time}


class TaskExecution(Base):
    __tablename__ = 'status_execution'
    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey('status_task.id'))

    start = Column(DateTime)
    end = Column(DateTime)
    succeeded = Column(Boolean, default=True)
    # Entry amounts
    produced = Column(Integer)
    accepted = Column(Integer)
    rejected = Column(Integer)
    failed = Column(Integer)
    abort_reason = Column(String, nullable=True)

    def __repr__(self):
        return (
            '<TaskExecution(task_id=%s,start=%s,end=%s,succeeded=%s,p=%s,a=%s,r=%s,f=%s,reason=%s)>'
            % (
                self.task_id,
                self.start,
                self.end,
                self.succeeded,
                self.produced,
                self.accepted,
                self.rejected,
                self.failed,
                self.abort_reason,
            )
        )

    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'start': self.start,
            'end': self.end,
            'succeeded': self.succeeded,
            'produced': self.produced,
            'accepted': self.accepted,
            'rejected': self.rejected,
            'failed': self.failed,
            'abort_reason': self.abort_reason,
        }


Index(
    'ix_status_execution_task_id_start_end_succeeded',
    TaskExecution.task_id,
    TaskExecution.start,
    TaskExecution.end,
    TaskExecution.succeeded,
)


@event('manager.db_cleanup')
def db_cleanup(manager, session):
    # Purge all status data for non existing tasks
    for status_task in session.query(StatusTask).all():
        if status_task.name not in manager.config['tasks']:
            log.verbose('Purging obsolete status data for task %s', status_task.name)
            session.delete(status_task)

    # Purge task executions older than 1 year
    result = (
        session.query(TaskExecution)
        .filter(TaskExecution.start < datetime.datetime.now() - timedelta(days=365))
        .delete()
    )
    if result:
        log.verbose('Removed %s task executions from history older than 1 year', result)


@with_session
def get_status_tasks(
    start=None, stop=None, order_by='last_execution_time', descending=True, session=None
):
    log.debug(
        'querying status tasks: start=%s, stop=%s, order_by=%s, descending=%s',
        start,
        stop,
        order_by,
        descending,
    )
    query = session.query(StatusTask)
    if descending:
        query = query.order_by(getattr(StatusTask, order_by).desc())
    else:
        query = query.order_by(getattr(StatusTask, order_by))
    return query.slice(start, stop).all()


@with_session
def get_executions_by_task_id(
    task_id,
    start=None,
    stop=None,
    order_by='start',
    descending=True,
    succeeded=None,
    produced=True,
    start_date=None,
    end_date=None,
    session=None,
):
    log.debug(
        'querying task executions: task_id=%s, start=%s, stop=%s, order_by=%s, descending=%s, succeeded=%s,'
        ' produced=%s, start_date=%s, end_date=%s',
        task_id,
        start,
        stop,
        order_by,
        descending,
        succeeded,
        produced,
        start_date,
        end_date,
    )
    query = session.query(TaskExecution).filter(TaskExecution.task_id == task_id)
    if succeeded:
        query = query.filter(TaskExecution.succeeded == succeeded)
    if produced:
        query = query.filter(TaskExecution.produced > 0)
    if start_date:
        query = query.filter(TaskExecution.start >= start_date)
    if end_date:
        query = query.filter(TaskExecution.start <= end_date)
    if descending:
        query = query.order_by(getattr(TaskExecution, order_by).desc())
    else:
        query = query.order_by(getattr(TaskExecution, order_by))
    return query.slice(start, stop).all()
