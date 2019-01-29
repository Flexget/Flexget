from __future__ import unicode_literals, division, absolute_import

from flexget import options
from flexget import plugin
from flexget.event import event
from flexget.manager import Session
from flexget.terminal import TerminalTable, table_parser, console, TerminalTableError

from . import db


def action_auth(options):
    if not (options.account):
        console(
            'You must specify an account (local identifier) so we know where to save your access token!'
        )
        return
    try:
        db.get_access_token(options.account, options.pin, re_auth=True, called_from_cli=True)
        console('Successfully authorized Flexget app on Trakt.tv. Enjoy!')
        return
    except plugin.PluginError as e:
        console('Authorization failed: %s' % e)


def action_list(options):
    with Session() as session:
        if not options.account:
            # Print all accounts
            accounts = session.query(db.TraktUserAuth).all()
            if not accounts:
                console('No trakt authorizations stored in database.')
                return
            header = ['Account', 'Created', 'Expires']
            table_data = [header]

            for auth in accounts:
                table_data.append(
                    [
                        auth.account,
                        auth.created.strftime('%Y-%m-%d'),
                        auth.expires.strftime('%Y-%m-%d'),
                    ]
                )
            try:
                table = TerminalTable(options.table_type, table_data)
                console(table.output)
                return
            except TerminalTableError as e:
                console('ERROR: %s' % str(e))

        # Show a specific account
        acc = (
            session.query(db.TraktUserAuth)
            .filter(db.TraktUserAuth.account == options.account)
            .first()
        )
        if acc:
            console('Authorization expires on %s' % acc.expires)
        else:
            console('Flexget has not been authorized to access your account.')


def action_refresh(options):
    if not options.account:
        console('Please specify an account')
        return
    try:
        db.get_access_token(options.account, refresh=True)
        console('Successfully refreshed your access token.')
        return
    except plugin.PluginError as e:
        console('Authorization failed: %s' % e)


def action_delete(options):
    if not options.account:
        console('Please specify an account')
        return
    try:
        db.delete_account(options.account)
        console('Successfully deleted your access token.')
        return
    except plugin.PluginError as e:
        console('Deletion failed: %s' % e)


def do_cli(manager, options):
    action_map = {
        'auth': action_auth,
        'list': action_list,
        'refresh': action_refresh,
        'delete': action_delete,
    }

    action_map[options.action](options)


@event('options.register')
def register_parser_arguments():
    acc_text = 'Local identifier which should be used in your config to refer these credentials'
    # Register subcommand
    parser = options.register_command(
        'trakt', do_cli, help='View and manage trakt authentication.'
    )
    # Set up our subparsers
    subparsers = parser.add_subparsers(title='actions', metavar='<action>', dest='action')
    auth_parser = subparsers.add_parser(
        'auth', help='Authorize Flexget to access your Trakt.tv account'
    )

    auth_parser.add_argument('account', metavar='<account>', help=acc_text)
    auth_parser.add_argument(
        'pin',
        metavar='<pin>',
        help='Get this by authorizing FlexGet to use your trakt account '
        'at %s. WARNING: DEPRECATED.' % db.PIN_URL,
        nargs='?',
    )

    show_parser = subparsers.add_parser(
        'list',
        help='List expiration date for Flexget authorization(s) (don\'t worry, '
        'they will automatically refresh when expired)',
        parents=[table_parser],
    )
    show_parser.add_argument('account', metavar='<account>', nargs='?', help=acc_text)

    refresh_parser = subparsers.add_parser(
        'refresh',
        help='Manually refresh your access token associated with your' ' --account <name>',
    )
    refresh_parser.add_argument('account', metavar='<account>', help=acc_text)

    delete_parser = subparsers.add_parser(
        'delete', help='Delete the specified <account> name from local database'
    )
    delete_parser.add_argument('account', metavar='<account>', help=acc_text)
