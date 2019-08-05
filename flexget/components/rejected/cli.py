from __future__ import unicode_literals, division, absolute_import

from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from flexget import options
from flexget import plugin
from flexget.event import event
from flexget.manager import Session
from flexget.terminal import TerminalTable, TerminalTableError, table_parser, console
from . import db

try:
    # NOTE: Importing other plugins is discouraged!
    from flexget.components.rejected import remember_rejected as plugin_remember_rejected
except ImportError:
    raise plugin.DependencyError(issued_by=__name__, missing='remember_rejected')


def do_cli(manager, options):
    if options.rejected_action == 'list':
        list_rejected(options)
    elif options.rejected_action == 'clear':
        clear_rejected(manager)


def list_rejected(options):
    with Session() as session:
        results = session.query(db.RememberEntry).all()
        header = ['#', 'Title', 'Task', 'Rejected by', 'Reason']
        table_data = [header]
        for entry in results:
            table_data.append(
                [entry.id, entry.title, entry.task.name, entry.rejected_by, entry.reason or '']
            )
    try:
        table = TerminalTable(options.table_type, table_data)
        table.table.justify_columns[0] = 'center'
        console(table.output)
    except TerminalTableError as e:
        console('ERROR: %s' % str(e))


def clear_rejected(manager):
    with Session() as session:
        results = session.query(db.RememberEntry).delete()
        console('Cleared %i items.' % results)
        session.commit()
        if results:
            manager.config_changed()


@event('options.register')
def register_parser_arguments():
    parser = options.register_command(
        'rejected', do_cli, help='list or clear remembered rejections'
    )
    subparsers = parser.add_subparsers(dest='rejected_action', metavar='<action>')
    subparsers.add_parser(
        'list', help='list all the entries that have been rejected', parents=[table_parser]
    )
    subparsers.add_parser(
        'clear', help='clear all rejected entries from database, so they can be retried'
    )
