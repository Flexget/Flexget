from __future__ import unicode_literals, division, absolute_import
import logging
import datetime
from datetime import timedelta

from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.schema import ForeignKey
from sqlalchemy.orm import relation

from flexget import db_schema, plugin
from flexget.event import event

from flexget.manager import Session

log = logging.getLogger('status')
Base = db_schema.versioned_base('status', 1)


@db_schema.upgrade('status')
def upgrade(ver, session):
    ver = 1
    # migrations
    return ver


class StatusTask(Base):
    __tablename__ = 'status_task'
    id = Column(Integer, primary_key=True)
    name = Column('task', String)
    executions = relation('TaskExecution', backref='task', cascade='all, delete, delete-orphan', lazy='dynamic')


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
        return ('<TaskExecution(task_id=%s,start=%s,end=%s,succeeded=%s,p=%s,a=%s,r=%s,f=%s,reason=%s)>' %
                (self.task_id, self.start, self.end, self.succeeded, self.produced, self.accepted,
                 self.rejected, self.failed, self.abort_reason))


class Status(object):
    """Track health status of tasks"""

    schema = {'type': 'boolean'}

    def __init__(self):
        self.execution = None

    def on_task_start(self, task, config):
        with Session() as session:
            st = session.query(StatusTask).filter(StatusTask.name == task.name).first()
            if not st:
                log.debug('Adding new task %s', task.name)
                st = StatusTask()
                st.name = task.name
                session.add(st)
                # TODO: purge removed tasks

        self.execution = TaskExecution()
        self.execution.start = datetime.datetime.now()
        self.execution.task = st

    @plugin.priority(-255)
    def on_task_input(self, task, config):
        self.execution.produced = len(task.entries)

    @plugin.priority(-255)
    def on_task_output(self, task, config):
        self.execution.accepted = len(task.accepted)
        self.execution.rejected = len(task.rejected)
        self.execution.failed = len(task.failed)

    def on_task_exit(self, task, config):
        with Session() as session:
            if self.execution is None:
                return
            if task.aborted:
                self.execution.succeeded = False
                self.execution.abort_reason = task.abort_reason
            self.execution.end = datetime.datetime.now()
            session.merge(self.execution)

    on_task_abort = on_task_exit


@event('manager.db_cleanup')
def db_cleanup(manager, session):
    result = session.query(TaskExecution).filter(
        TaskExecution.start < datetime.datetime.now() - timedelta(days=365)).delete()
    if result:
        log.verbose('Removed %s task executions from history older than 1 year', result)


@event('plugin.register')
def register_plugin():
    plugin.register(Status, 'status', builtin=True, api_ver=2)
