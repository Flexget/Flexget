from argparse import ArgumentParser

from flexget import options
from flexget.db_schema import plugin_schemas, reset_schema
from flexget.event import event
from flexget.manager import Base, Session
from flexget.terminal import console


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
    plugin = options.plugin_name[0]
    try:
        reset_schema(plugin)
        console('The database for `%s` has been reset.' % plugin)
    except ValueError as e:
        console('Unable to reset %s: %s' % (plugin, e.message))


@event('options.register')
def register_parser_arguments():
    plugins_parser = ArgumentParser(add_help=False)
    plugins_parser.add_argument(
        'plugin_name', help="Name of plugin to reset", nargs=1, choices=list(plugin_schemas)
    )

    parser = options.register_command(
        'database', do_cli, help='Utilities to manage the FlexGet database'
    )
    subparsers = parser.add_subparsers(title='Actions', metavar='<action>', dest='db_action')
    subparsers.add_parser(
        'cleanup', help='Make all plugins clean un-needed data from the database'
    )
    subparsers.add_parser(
        'vacuum', help='Running vacuum can increase performance and decrease database size'
    )
    reset_parser = subparsers.add_parser(
        'reset', add_help=False, help='Reset the entire database (DANGEROUS!)'
    )
    reset_parser.add_argument(
        '--sure',
        action='store_true',
        required=True,
        help='You must use this flag to indicate you REALLY want to do this',
    )
    subparsers.add_parser(
        'reset-plugin', help='Reset the database for a specific plugin', parents=[plugins_parser]
    )
