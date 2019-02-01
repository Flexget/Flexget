from __future__ import unicode_literals, division, absolute_import

import datetime
from builtins import *  # noqa
from datetime import timedelta

from colorclass.toggles import disable_all_colors
from sqlalchemy import desc
from sqlalchemy.orm.exc import NoResultFound

from flexget import options
from flexget.event import event
from flexget.manager import Session
from flexget.terminal import TerminalTable, TerminalTableError, table_parser, colorize, console
from . import db


def do_cli(manager, options):
    if options.table_type == 'porcelain':
        disable_all_colors()
    if options.task:
        do_cli_task(manager, options)
    else:
        do_cli_summary(manager, options)


def do_cli_task(manager, options):
    header = ['Start', 'Duration', 'Produced', 'Accepted', 'Rejected', 'Failed', 'Abort Reason']
    table_data = [header]
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

                table_data.append(
                    [
                        start,
                        duration,
                        ex.produced,
                        ex.accepted,
                        ex.rejected,
                        ex.failed,
                        ex.abort_reason if ex.abort_reason is not None else '',
                    ]
                )

    try:
        table = TerminalTable(options.table_type, table_data)
        console(table.output)
    except TerminalTableError as e:
        console('ERROR: %s' % str(e))


def do_cli_summary(manager, options):
    header = [
        'Task',
        'Last execution',
        'Last success',
        'Produced',
        'Accepted',
        'Rejected',
        'Failed',
        'Duration',
    ]
    table_data = [header]

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

            table_data.append(
                [
                    task.name,
                    last_exec,
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
    except TerminalTableError as e:
        console('ERROR: %s' % str(e))


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
