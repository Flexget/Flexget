import datetime
import fnmatch
from datetime import timedelta

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import aliased
from sqlalchemy.orm.exc import NoResultFound

from flexget import options
from flexget.event import event
from flexget.manager import Session
from flexget.terminal import TerminalTable, colorize, console, disable_colors, table_parser

from . import db


def do_cli(manager, options):
    if options.table_type == 'porcelain':
        disable_colors()
    if options.status_action == 'remove':
        do_cli_remove(manager, options)
        return
    if options.task:
        do_cli_task(manager, options)
    else:
        do_cli_summary(manager, options)


def do_cli_task(manager, options):
    header = ['Start', 'Duration', 'Entries', 'Accepted', 'Rejected', 'Failed', 'Abort Reason']
    table = TerminalTable(*header, table_type=options.table_type)
    with Session() as session:
        try:
            task = session.query(db.StatusTask).filter(db.StatusTask.name == options.task).one()
        except NoResultFound:
            console(f'Task name `{options.task}` does not exists or does not have any records')
            return
        else:
            query = task.executions.order_by(desc(db.TaskExecution.start))[: options.limit]
            for ex in reversed(query):
                start = ex.start.strftime('%Y-%m-%d %H:%M')
                start = colorize('green', start) if ex.succeeded else colorize('red', start)

                if ex.end is not None and ex.start is not None:
                    delta = ex.end - ex.start
                    duration = f'{delta.total_seconds():1.0f}s'
                else:
                    duration = '?'

                table.add_row(
                    start,
                    duration,
                    str(ex.produced),
                    str(ex.accepted),
                    str(ex.rejected),
                    str(ex.failed),
                    ex.abort_reason if ex.abort_reason is not None else '',
                )
    console(table)


def do_cli_summary(manager, options):
    header = [
        'Task',
        'Last execution',
        'Last success',
        'Entries',
        'Accepted',
        'Rejected',
        'Failed',
        'Duration',
    ]
    table = TerminalTable(*header, table_type=options.table_type)

    with Session() as session:
        # Create aliases for different execution queries
        LastExecution = aliased(db.TaskExecution)  # noqa: N806
        LastSuccess = aliased(db.TaskExecution)  # noqa: N806

        # Subquery to find the last execution time for each task
        last_execution_subq = (
            session
            .query(LastExecution.task_id, func.max(LastExecution.start).label('last_start'))
            .group_by(LastExecution.task_id)
            .subquery()
        )

        # Subquery to find the last successful execution with produced > 0 for each task
        last_success_subq = (
            session
            .query(LastSuccess.task_id, func.max(LastSuccess.start).label('last_success_start'))
            .filter(and_(LastSuccess.succeeded, LastSuccess.produced > 0))
            .group_by(LastSuccess.task_id)
            .subquery()
        )

        # Main query with left joins to get all required data in a single query
        query = (
            session
            .query(
                db.StatusTask,
                last_execution_subq.c.last_start,
                LastSuccess.start,
                LastSuccess.end,
                LastSuccess.produced,
                LastSuccess.accepted,
                LastSuccess.rejected,
                LastSuccess.failed,
            )
            .outerjoin(last_execution_subq, db.StatusTask.id == last_execution_subq.c.task_id)
            .outerjoin(last_success_subq, db.StatusTask.id == last_success_subq.c.task_id)
            .outerjoin(
                LastSuccess,
                and_(
                    LastSuccess.task_id == db.StatusTask.id,
                    LastSuccess.start == last_success_subq.c.last_success_start,
                    LastSuccess.succeeded,
                    LastSuccess.produced > 0,
                ),
            )
        )

        for row in query.all():
            (
                task,
                last_exec_time,
                success_start,
                success_end,
                produced,
                accepted,
                rejected,
                failed,
            ) = row

            # Process last execution time
            # Fix weird issue that a task registers StatusTask but without an execution. GH #2022
            last_exec = last_exec_time.strftime('%Y-%m-%d %H:%M') if last_exec_time else '-'

            # Process last success data
            if success_start is None:
                duration = None
                last_success = '-'
            else:
                duration = success_end - success_start if success_end else None
                last_success = success_start.strftime('%Y-%m-%d %H:%M')

                age = datetime.datetime.utcnow() - success_start
                if age > timedelta(days=7):
                    last_success = colorize('red', last_success)
                elif age < timedelta(minutes=10):
                    last_success = colorize('green', last_success)

            table.add_row(
                task.name,
                last_exec,
                last_success,
                str(produced) if produced is not None else '-',
                str(accepted) if accepted is not None else '-',
                str(rejected) if rejected is not None else '-',
                str(failed) if failed is not None else '-',
                f'{duration.total_seconds():1.0f}s' if duration is not None else '-',
            )

    console(table)


def do_cli_remove(manager, options):
    with Session() as session:
        all_tasks = session.query(db.StatusTask).all()
        pattern = options.task_name.lower()
        matching_tasks = [
            task for task in all_tasks if fnmatch.fnmatchcase(task.name.lower(), pattern)
        ]
        if not matching_tasks:
            console(f'Task pattern `{options.task_name}` does not match any tasks')
            return
        task_names = []
        for task in matching_tasks:
            console(f'Removing task `{task.name}` ...')
            session.delete(task)
            task_names.append(task.name)
        session.commit()


@event('options.register')
def register_parser_arguments():
    parser = options.register_command(
        'status', do_cli, help='View task health status', parents=[table_parser]
    )
    subparsers = parser.add_subparsers(
        title='actions', metavar='<action>', dest='status_action', required=False
    )
    remove_parser = subparsers.add_parser(
        'remove',
        help='Remove a task and all its execution records. Supports glob pattern matching.',
    )
    remove_parser.add_argument(
        'task_name',
        metavar='TASK',
        help='Name or glob pattern of the task(s) to remove (e.g., "task-*")',
    )
    parser.add_argument(
        '--task', action='store', metavar='TASK', help='Limit to results in specified %(metavar)s'
    )
    parser.add_argument(
        '--limit',
        action='store',
        type=int,
        metavar='NUM',
        default=50,
        help='Limit to %(metavar)s results',
    )
