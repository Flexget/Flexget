from __future__ import unicode_literals, division, absolute_import

from flexget import options
from flexget.db_schema import reset_schema, plugin_schemas
from flexget.event import event
from flexget.logger import console
from flexget.manager import Base, Session


def do_cli(manager, options):
    with manager.acquire_lock():
        if options.db_action == 'cleanup':
            cleanup(manager)
        elif options.db_action == 'vacuum':
            vacuum()
        elif options.db_action == 'reset':
            reset(manager)
        elif options.db_action == 'reset-plugin':
            reset_plugin(options)


def cleanup(manager):
    manager.db_cleanup(force=True)
    console('Database cleanup complete.')


def vacuum():
    console('Running VACUUM on sqlite database, this could take a while.')
    session = Session()
    try:
        session.execute('VACUUM')
        session.commit()
    finally:
        session.close()
    console('VACUUM complete.')


def reset(manager):
    Base.metadata.drop_all(bind=manager.engine)
    Base.metadata.create_all(bind=manager.engine)
    console('The FlexGet database has been reset.')


def reset_plugin(options):
    plugin = options.reset_plugin
    if not plugin:
        if options.porcelain:
            console('%-20s | Ver | Tables' % 'Name')
        else:
            console('-' * 79)
            console('%-20s Ver  Tables' % 'Name')
            console('-' * 79)
        for k, v in sorted(plugin_schemas.iteritems()):
            tables = ''
            line_len = 0
            for name in v['tables']:
                if options.porcelain:
                    pass
                else:
                    if line_len + len(name) + 2 >= 53:
                        tables += '\n'
                        tables += ' ' * 26
                        line_len = len(name) + 2
                    else:
                        line_len += len(name) + 2
                tables += name + ', '
            tables = tables.rstrip(', ')
            if options.porcelain:
                console('%-20s %s %-3s %s %s' % (k, '|', v['version'], '|', tables))
            else:
                console('%-20s %-2s   %s' % (k, v['version'], tables))
    else:
        try:
            reset_schema(plugin)
            console('The database for `%s` has been reset.' % plugin)
        except ValueError as e:
            console('Unable to reset %s: %s' % (plugin, e.message))


@event('options.register')
def register_parser_arguments():
    parser = options.register_command('database', do_cli, help='utilities to manage the FlexGet database')
    subparsers = parser.add_subparsers(title='Actions', metavar='<action>', dest='db_action')
    subparsers.add_parser('cleanup', help='make all plugins clean un-needed data from the database')
    subparsers.add_parser('vacuum', help='running vacuum can increase performance and decrease database size')
    reset_parser = subparsers.add_parser('reset', add_help=False, help='reset the entire database (DANGEROUS!)')
    reset_parser.add_argument('--sure', action='store_true', required=True,
                              help='you must use this flag to indicate you REALLY want to do this')
    reset_plugin_parser = subparsers.add_parser('reset-plugin', help='reset the database for a specific plugin')
    reset_plugin_parser.add_argument('reset_plugin', metavar='<plugin>', nargs='?',
                                 help='name of plugin to reset (if omitted, known plugins will be listed)')
    reset_plugin_parser.add_argument('--porcelain', action='store_true', help='make the output parseable')
