from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

from flexget import options, plugin
from flexget.event import event
from flexget.terminal import console
from flexget.manager import Session

try:
    from flexget.plugins.internal.api_t411 import (T411Proxy)
except:
    raise plugin.DependencyError(issued_by='cli_series', missing='api_t411',
                                 message='Torrent411 commandline interface not loaded')


def do_cli(manager, options):
    """
    Dispach cli action
    :param manager:
    :param options:
    :return:
    """
    if options.t411_action == 'list-cats':
        print_categories(parent_category_name=options.category)
    elif options.t411_action == 'add-auth':
        add_credential(username=options.username, password=options.password)
    elif options.t411_action == 'list-auth':
        pass
    elif options.t411_action == 'list-terms':
        print_terms(category_name=options.category, term_type_name=options.type)


def add_credential(username, password):
    """
    Add (or update) credential into database
    :param username:
    :param password:
    :return:
    """
    proxy = T411Proxy()
    is_new = proxy.add_credential(username=username, password=password)
    if is_new:
        console('Credential successfully added')
    else:
        console('Credential successfully updated')


def print_terms(category_name=None, term_type_name=None):
    proxy = T411Proxy()
    proxy.set_credential()
    formatting_main = '%-60s %-5s %-5s'
    formatting_sub = '     %-55s %-5s %-5s'
    console(formatting_main % ('Name', 'PID', 'ID'))

    if term_type_name:
        console("Not yet implemented !")
    else:
        with Session() as session:
            categories = proxy.find_categories(category_name=category_name, is_sub_category=True, session=session)
            for category in categories:
                console(formatting_main % (category.name, category.parent_id, category.id))
                for term_type in category.term_types:
                    console(formatting_main % (term_type.name, '', term_type.id))
                    for term in term_type.terms:
                        console(formatting_sub % (term.name, term_type.id, term.id))


def print_categories(parent_category_name=None):
    """
    Print category and its sub-categories
    :param parent_category_name: if None, all categories will be displayed
    :return:
    """
    proxy = T411Proxy()
    proxy.set_credential()
    with Session() as session:
        if parent_category_name is None:
            categories = proxy.main_categories(session=session)
        else:
            categories = proxy.find_categories(parent_category_name, session=session)
        formatting_main = '%-30s %-5s %-5s'
        formatting_sub = '     %-25s %-5s %-5s'
        console(formatting_main % ('Category name', 'PID', 'ID'))
        for category in categories:
            console(formatting_main % (category.name, category.parent_id, category.id))
            for sub_category in category.sub_categories:
                console(formatting_sub % (sub_category.name, sub_category.parent_id, sub_category.id))


@event('options.register')
def register_parser_arguments():
    # Register the command
    parser = options.register_command('t411', do_cli, help='view and manipulate the Torrent411 plugin database')

    # Set up our subparsers
    action_parsers = parser.add_subparsers(title='actions', metavar='<action>', dest='t411_action')
    auth_parser = action_parsers.add_parser('add-auth', help='authorize Flexget to access your Torrent411 account')
    auth_parser.add_argument('username', metavar='<username>', help='Your t411 username')
    auth_parser.add_argument('password', metavar='<password>', help='Your t411 password')

    list_categories_parser = action_parsers.add_parser('list-cats', help='list available categories on Torrent411')
    list_categories_parser.add_argument('category',
                                        nargs='?',
                                        metavar='<category>',
                                        help='limit list to all, main or sub categories (default: %(default)s)')

    list_terms = action_parsers.add_parser('list-terms', help='list available terms usable on Torrent411')
    list_terms.add_argument('--category', help='show terms only for this category')
    list_terms.add_argument('--type', help='show terms only for this term type')
