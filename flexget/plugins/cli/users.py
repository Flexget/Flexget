from __future__ import unicode_literals, division, absolute_import

from flexget import options, plugin
from flexget.event import event
from flexget.logger import console
from flexget.utils.database import with_session

try:
    from flexget.webserver import User, generate_key, user_exist, change_password, generate_token, WeakPassword
except ImportError:
    raise plugin.DependencyError(issued_by='cli_series', missing='webserver',
                                 message='Users commandline interface not loaded')


@with_session
def do_cli(manager, options, session=None):
    if hasattr(options, 'user'):
        options.user = options.user.lower()

    if options.action == 'passwd':
        user = user_exist(name=options.user, session=session)
        if not user:
            console('User %s does not exist' % options.user)
            return
        try:
            change_password(user_name=user.name, password=options.password, session=session)
        except WeakPassword as e:
            console(e.value)
            return
        console('Updated password for user %s' % options.user)

    if options.action == 'gentoken':
        user = user_exist(name=options.user, session=session)
        if not user:
            console('User %s does not exist' % options.user)
            return
        user = generate_token(user_name=user.name, session=session)
        console('Generated new token for user %s' % user.name)
        console('Token %s' % user.token)


@event('options.register')
def register_parser_arguments():
    parser = options.register_command('users', do_cli, help='Manage users providing access to the web server')
    subparsers = parser.add_subparsers(dest='action', metavar='<action>')

    pwd_parser = subparsers.add_parser('passwd', help='change password for user')
    pwd_parser.add_argument('user', metavar='<username>', help='User to change password')
    pwd_parser.add_argument('password', metavar='<new password>', help='New Password')

    gentoken_parser = subparsers.add_parser('gentoken', help='Generate a new api token for a user')
    gentoken_parser.add_argument('user', metavar='<username>', help='User to regenerate api token')
