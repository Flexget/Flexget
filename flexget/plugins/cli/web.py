from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

from flexget import options
from flexget.event import event
from flexget.terminal import console
from flexget.utils.database import with_session
from flexget.webserver import change_password, generate_token, WeakPassword, get_user


@with_session
def do_cli(manager, options, session=None):
    if options.action == 'passwd':
        try:
            change_password(password=options.password, session=session)
        except WeakPassword as e:
            console(e.value)
            return
        console('Updated password')

    if options.action == 'gentoken':
        token = generate_token(session=session)
        console('Generated new token %s' % token)

    if options.action == 'showtoken':
        user = get_user()
        console('Token: %s' % user.token)


@event('options.register')
def register_parser_arguments():
    parser = options.register_command('web', do_cli, help='Manage web server settings')
    subparsers = parser.add_subparsers(dest='action', metavar='<action>')

    pwd_parser = subparsers.add_parser('passwd', help='change password for web server')
    pwd_parser.add_argument('password', metavar='<new password>', help='New Password')

    subparsers.add_parser('gentoken', help='Generate a new api token')
    subparsers.add_parser('showtoken', help='Show api token')
