import datetime
from datetime import timedelta

from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.manager import Session

from . import db

logger = logger.bind(name='status')


class Status:
    """Track health status of tasks"""

    schema = {'type': 'boolean'}

    def __init__(self):
        self.execution = None

    def on_task_start(self, task, config):
        with Session() as session:
            st = session.query(db.StatusTask).filter(db.StatusTask.name == task.name).first()
            if not st:
                logger.debug('Adding new task {}', task.name)
                st = db.StatusTask()
                st.name = task.name
                session.add(st)

        self.execution = db.TaskExecution()
        self.execution.start = datetime.datetime.now()
        self.execution.task = st

    @plugin.priority(plugin.PRIORITY_LAST)
    def on_task_input(self, task, config):
        self.execution.produced = len(task.entries)

    @plugin.priority(plugin.PRIORITY_LAST)
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
    # Purge all status data for non existing tasks
    for status_task in session.query(db.StatusTask).all():
        if status_task.name not in manager.config['tasks']:
            logger.verbose('Purging obsolete status data for task {}', status_task.name)
            session.delete(status_task)

    # Purge task executions older than 1 year
    result = (
        session.query(db.TaskExecution)
        .filter(db.TaskExecution.start < datetime.datetime.now() - timedelta(days=365))
        .delete()
    )
    if result:
        logger.verbose('Removed {} task executions from history older than 1 year', result)


@event('plugin.register')
def register_plugin():
    plugin.register(Status, 'status', builtin=True, api_ver=2)
