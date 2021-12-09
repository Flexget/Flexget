import datetime
from datetime import timedelta

from sqlalchemy import desc
from sqlalchemy.orm.exc import NoResultFound

from flexget import options
from flexget.event import event
from flexget.manager import Session
from flexget.terminal import TerminalTable, colorize, console, disable_colors, table_parser

from . import db


def do_cli(manager, options):
    if options.table_type == 'porcelain':
        disable_colors()
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
            console('Task name `%s` does not exists or does not have any records' % options.task)
            return
        else:
            query = task.executions.order_by(desc(db.TaskExecution.start))[: options.limit]
            for ex in reversed(query):
                start = ex.start.strftime('%Y-%m-%d %H:%M')
                start = colorize('green', start) if ex.succeeded else colorize('red', start)

                if ex.end is not None and ex.start is not None:
                    delta = ex.end - ex.start
                    duration = '%1.fs' % delta.total_seconds()
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
        for task in session.query(db.StatusTask).all():
            ok = (
                session.query(db.TaskExecution)
                .filter(db.TaskExecution.task_id == task.id)
                .filter(db.TaskExecution.succeeded == True)
                .filter(db.TaskExecution.produced > 0)
                .order_by(db.TaskExecution.start.desc())
                .first()
            )

            if ok is None:
                duration = None
                last_success = '-'
            else:
                duration = ok.end - ok.start
                last_success = ok.start.strftime('%Y-%m-%d %H:%M')

                age = datetime.datetime.utcnow() - ok.start
                if age > timedelta(days=7):
                    last_success = colorize('red', last_success)
                elif age < timedelta(minutes=10):
                    last_success = colorize('green', last_success)
            # Fix weird issue that a task registers StatusTask but without an execution. GH #2022
            last_exec = (
                task.last_execution_time.strftime('%Y-%m-%d %H:%M')
                if task.last_execution_time
                else '-'
            )

            table.add_row(
                task.name,
                last_exec,
                last_success,
                str(ok.produced) if ok is not None else '-',
                str(ok.accepted) if ok is not None else '-',
                str(ok.rejected) if ok is not None else '-',
                str(ok.failed) if ok is not None else '-',
                '%1.fs' % duration.total_seconds() if duration is not None else '-',
            )

    console(table)


@event('options.register')
def register_parser_arguments():
    parser = options.register_command(
        'status', do_cli, help='View task health status', parents=[table_parser]
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
