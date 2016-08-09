from __future__ import unicode_literals, division, absolute_import


from flexget import options, plugin
from flexget.event import event
from flexget.logger import console
from flexget.manager import Session
from flexget.plugins.internal.api_trakt import get_access_token, TraktUserAuth, delete_account, PIN_URL


def action_auth(options):
    if not (options.account):
        console('You must specify an account (local identifier) so we know where to save your access token!')
        return
    try:
        get_access_token(options.account, options.pin, re_auth=True, called_from_cli=True)
        console('Successfully authorized Flexget app on Trakt.tv. Enjoy!')
        return
    except plugin.PluginError as e:
        console('Authorization failed: %s' % e)


def action_list(options):
    with Session() as session:
        if not options.account:
            # Print all accounts
            accounts = session.query(TraktUserAuth).all()
            if not accounts:
                console('No trakt authorizations stored in database.')
                return
            console('{:-^21}|{:-^28}|{:-^28}'.format('Account', 'Created', 'Expires'))
            for auth in accounts:
                console('{:<21}|{:>28}|{:>28}'.format(
                    auth.account, auth.created.strftime('%Y-%m-%d'), auth.expires.strftime('%Y-%m-%d')))
            return
        # Show a specific account
        acc = session.query(TraktUserAuth).filter(TraktUserAuth.account == options.account).first()
        if acc:
            console('Authorization expires on %s' % acc.expires)
        else:
            console('Flexget has not been authorized to access your account.')


def action_refresh(options):
    if not options.account:
        console('Please specify an account')
        return
    try:
        get_access_token(options.account, refresh=True)
        console('Successfully refreshed your access token.')
        return
    except plugin.PluginError as e:
        console('Authorization failed: %s' % e)


def action_delete(options):
    if not options.account:
        console('Please specify an account')
        return
    try:
        delete_account(options.account)
        console('Successfully deleted your access token.')
        return
    except plugin.PluginError as e:
        console('Deletion failed: %s' % e)


def do_cli(manager, options):
    action_map = {
        'auth': action_auth,
        'list': action_list,
        'refresh': action_refresh,
        'delete': action_delete
    }

    action_map[options.action](options)


@event('options.register')
def register_parser_arguments():
    acc_text = 'local identifier which should be used in your config to refer these credentials'
    # Register subcommand
    parser = options.register_command('trakt', do_cli, help='view and manage trakt authentication.')
    # Set up our subparsers
    subparsers = parser.add_subparsers(title='actions', metavar='<action>', dest='action')
    auth_parser = subparsers.add_parser('auth', help='authorize Flexget to access your Trakt.tv account')

    auth_parser.add_argument('account', metavar='<account>', help=acc_text)
    auth_parser.add_argument('pin', metavar='<pin>', help='get this by authorizing FlexGet to use your trakt account '
                                                          'at %s. WARNING: DEPRECATED.' % PIN_URL, nargs='?')

    show_parser = subparsers.add_parser('list', help='list expiration date for Flexget authorization(s) (don\'t worry, '
                                                     'they will automatically refresh when expired)')
    show_parser.add_argument('account', metavar='<account>', nargs='?', help=acc_text)

    refresh_parser = subparsers.add_parser('refresh', help='manually refresh your access token associated with your'
                                                           ' --account <name>')
    refresh_parser.add_argument('account', metavar='<account>', help=acc_text)

    delete_parser = subparsers.add_parser('delete', help='delete the specified <account> name from local database')
    delete_parser.add_argument('account', metavar='<account>', help=acc_text)
