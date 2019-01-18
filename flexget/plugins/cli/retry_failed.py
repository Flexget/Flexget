from __future__ import unicode_literals, division, absolute_import

from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from flexget import options
from flexget import plugin
from flexget.event import event
from flexget.manager import Session
from flexget.terminal import TerminalTable, TerminalTableError, table_parser, console

try:
    # NOTE: Importing other plugins is discouraged!
    from flexget.plugins.filter import retry_failed as plugin_retry_failed
except ImportError:
    raise plugin.DependencyError(
        issued_by=__name__, missing='retry_failed',
    )


def do_cli(manager, options):
    if options.failed_action == 'list':
        list_failed(options)
    elif options.failed_action == 'clear':
        clear_failed(manager)


def list_failed(options):
    with Session() as session:
        results = session.query(plugin_retry_failed.FailedEntry).all()
        header = ['#', 'Title', 'Fail count', 'Reason', 'Failure time']
        table_data = [header]
        for entry in results:
            table_data.append(
                [entry.id, entry.title, entry.count, '' if entry.reason == 'None' else entry.reason,
                 entry.tof.strftime('%Y-%m-%d %H:%M')])
    try:
        table = TerminalTable(options.table_type, table_data, wrap_columns=[3, 1])
    except TerminalTableError as e:
        console('ERROR: %s' % str(e))
    else:
        table.table.justify_columns[0] = 'center'
        console(table.output)


def clear_failed(manager):
    with Session() as session:
        results = session.query(plugin_retry_failed.FailedEntry).delete()
        console('Cleared %i items.' % results)
        session.commit()
        if results:
            manager.config_changed()


@event('options.register')
def register_parser_arguments():
    parser = options.register_command('failed', do_cli, help='list or clear remembered failures')
    subparsers = parser.add_subparsers(dest='failed_action', metavar='<action>')
    subparsers.add_parser('list', help='list all the entries that have had failures', parents=[table_parser])
    subparsers.add_parser('clear', help='clear all failures from database, so they can be retried')
