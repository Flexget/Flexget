from flexget import options, plugin
from flexget.event import event
from flexget.manager import Session
from flexget.terminal import TerminalTable, console, table_parser

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
        table = TerminalTable(*header, table_type=options.table_type)
        for entry in results:
            table.add_row(
                str(entry.id), entry.title, entry.task.name, entry.rejected_by, entry.reason or ''
            )
    console(table)


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
