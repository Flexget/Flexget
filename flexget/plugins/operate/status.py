from __future__ import unicode_literals, division, absolute_import
import logging
import datetime
from datetime import timedelta

from colorclass.color import Color

from sqlalchemy import Column, Integer, String, DateTime, Boolean, desc
from sqlalchemy.schema import Table, ForeignKey
from sqlalchemy.orm import relation
from sqlalchemy.orm.exc import NoResultFound

from flexget import db_schema, options, plugin
from flexget.event import event
from flexget.logger import console
from flexget.terminal import TerminalTable, CLITableError, table_parser
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
        self.execution.start = datetime.datetime.utcnow()
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
            self.execution.end = datetime.datetime.utcnow()
            session.merge(self.execution)

    on_task_abort = on_task_exit


def do_cli(manager, options):
    if options.task:
        do_cli_task(manager, options)
    else:
        do_cli_summary(manager, options)


def do_cli_task(manager, options):
    header = ['Start', 'Duration', 'Produced', 'Accepted', 'Rejected', 'Failed', 'Abort Reason']
    table_data = [header]
    with Session() as session:
        try:
            task = session.query(StatusTask).filter(StatusTask.name==options.task).one()
        except NoResultFound:
            console('Task name `%s` does not exists or does not have any records' % options.task)
        else:
            query = task.executions.order_by(desc(TaskExecution.start))[:options.limit]
            for ex in reversed(query):
                start = ex.start.strftime('%Y-%m-%d %H:%M')
                if ex.succeeded:
                    start = Color('{green}%s{/green}' % start)
                else:
                    start = Color('{red}%s{/red}' % start)

                if ex.end is not None and ex.start is not None:
                    delta = ex.end - ex.start
                    duration = '%1.fs' % delta.total_seconds()
                else:
                    duration = '?'

                table_data.append(
                    [
                        start,
                        duration,
                        ex.produced,
                        ex.accepted,
                        ex.rejected,
                        ex.failed,
                        ex.abort_reason if ex.abort_reason is not None else ''
                    ]
                )


    table = TerminalTable(options.table_type, table_data)
    try:
        console(table.output)
    except CLITableError as e:
        console('ERROR: %s' % str(e))


def do_cli_summary(manager, options):
    header= ['Task', 'Last success', 'Produced', 'Accepted', 'Rejected', 'Failed', 'Duration']
    table_data = [header]

    with Session() as session:
        for task in session.query(StatusTask).all():
            ok = session.query(TaskExecution).\
                filter(TaskExecution.task_id == task.id).\
                filter(TaskExecution.succeeded == True).\
                filter(TaskExecution.produced > 0).\
                order_by(TaskExecution.start.desc()).first()

            if ok is None:
                duration = None
                last_success = '-'
            else:
                duration = ok.end - ok.start
                last_success = ok.start.strftime('%Y-%m-%d %H:%M')

                age = datetime.datetime.utcnow() - ok.start
                if age > timedelta(days=7):
                    last_success = Color('{red}%s{/red}' % last_success)
                elif age < timedelta(minutes=10):
                    last_success = Color('{green}%s{/green}' % last_success)

            table_data.append([
              task.name,
              last_success,
              ok.produced if ok is not None else '-',
              ok.accepted if ok is not None else '-',
              ok.rejected if ok is not None else '-',
              ok.failed if ok is not None else '-',
              '%1.fs' % duration.total_seconds() if duration is not None else '-',
              ]
            )

    table = TerminalTable(options.table_type, table_data)
    try:
        console(table.output)
    except CLITableError as e:
        console('ERROR: %s' % str(e))


@event('manager.db_cleanup')
def db_cleanup(manager, session):
    result = session.query(TaskExecution).filter(TaskExecution.start < datetime.datetime.utcnow() - timedelta(days=365)).delete()
    if result:
        log.verbose('Removed %s task executions from history older than 1 year', result)


@event('plugin.register')
def register_plugin():
    plugin.register(Status, 'status', builtin=True, api_ver=2)


@event('options.register')
def register_parser_arguments():
    parser = options.register_command('status', do_cli, help='View task health status', parents=[table_parser])
    parser.add_argument('--task', action='store', metavar='TASK', help='Limit to results in specified %(metavar)s')
    parser.add_argument('--limit', action='store', type=int, metavar='NUM', default=50,
                         help='Limit to %(metavar)s results')
