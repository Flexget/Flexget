from __future__ import unicode_literals, division, absolute_import

from argparse import ArgumentParser

from sqlalchemy.orm.exc import NoResultFound

from flexget import options
from flexget.event import event
from flexget.logger import console
from flexget.manager import Session
from flexget.plugins.list.entry_list import get_entry_lists, get_list_by_exact_name, get_entries_by_list_id, \
    get_entry_by_id, get_entry_by_title, EntryListList, EntryListEntry


def parse_identifier(identifier_string):
    if identifier_string.count('=') != 1:
        return
    name, value = identifier_string.split('=', 2)
    return {name: value}


def do_cli(manager, options):
    """Handle entry-list subcommand"""
    if options.list_action == 'all':
        entry_list_lists()
        return

    if options.list_action == 'list':
        entry_list_list(options)
        return

    if options.list_action == 'show':
        entry_list_show(options)
        return

    if options.list_action == 'add':
        entry_list_add(options)
        return

    if options.list_action == 'del':
        movie_list_del(options)
        return

    if options.list_action == 'purge':
        movie_list_purge(options)
        return


def entry_list_lists():
    """ Show all entry lists """
    with Session() as session:
        lists = get_entry_lists(session=session)
        console('Existing entry lists:')
        console('-' * 20)
        for entry_list in lists:
            console(entry_list.name)


def entry_list_list(options):
    """List entry list"""
    with Session() as session:
        try:
            entry_list = get_list_by_exact_name(options.list_name, session=session)
        except NoResultFound:
            console('Could not find entry list with name {}'.format(options.list_name))
            return
        console('Entries for list `{}`:'.format(options.list_name))
        console('-' * 79)
        for entry in get_entries_by_list_id(entry_list.id, order_by='added', descending=True, session=session):
            console('{:2d}: {}, {} fields'.format(entry.id, entry.title, len(entry.entry)))


def entry_list_show(options):
    with Session() as session:
        try:
            entry_list = get_list_by_exact_name(options.list_name, session=session)
        except NoResultFound:
            console('Could not find entry list with name {}'.format(options.list_name))
            return

        try:
            entry = get_entry_by_id(entry_list.id, int(options.entry), session=session)
        except NoResultFound:
            console(
                'Could not find matching entry with ID {} in list `{}`'.format(int(options.entry), options.list_name))
            return
        except ValueError:
            entry = get_entry_by_title(entry_list.id, options.entry, session=session)
            if not entry:
                console(
                    'Could not find matching entry with title `{}` in list `{}`'.format(options.entry,
                                                                                        options.list_name))
                return

        console('Showing fields for entry ID {}'.format(options.list_name))
        console('-' * 79)
        for k, v in sorted(entry.entry.items()):
            console('{}: {}'.format(k.upper(), v))


def entry_list_add(options):
    with Session() as session:
        try:
            entry_list = get_list_by_exact_name(options.list_name, session=session)
        except NoResultFound:
            console('Could not find entry list with name `{}`, creating'.format(options.list_name))
            entry_list = EntryListList(name=options.list_name)
            session.add(entry_list)
        session.merge(entry_list)

        title = options.entry_title
        entry = {'title': options.entry_title, 'original_url': options.original_url}
        db_entry = get_entry_by_title(list_id=entry_list.id, title=title, session=session)
        if db_entry:
            console("Entry with the title `{}` already exist with list `{}`. Will replace identifiers if given".format(
                title, entry_list.name))
            output = 'Successfully updated entry `{}` to entry list `{}` '.format(title, entry_list.name)
        else:
            console("Adding entry with title `{}` to list `{}`".format(title, entry_list.name))
            db_entry = EntryListEntry(entry=entry, entry_list_id=entry_list.id)
            session.add(db_entry)
            output = 'Successfully added entry `{}` to entry list `{}` '.format(title, entry_list.name)
        if options.identifiers:
            output = 'Successfully updated entry `{}` to entry list `{}` '.format(title, entry_list.name)
            identifiers = [parse_identifier(identifier) for identifier in options.identifiers if options.identifiers]
            console('Adding identifiers to entry `{}`'.format(title))
            for identifier in identifiers:
                for k, v in identifier.items():
                    entry[k] = v
            db_entry.entry = entry
        console(output)


def movie_list_del(options):
    with Session() as session:
        try:
            entry_list = get_list_by_exact_name(options.list_name)
        except NoResultFound:
            console('Could not find entry list with name `{}`'.format(options.list_name))
            return
        try:
            db_entry = get_entry_by_id(entry_list.id, int(options.entry), session=session)
        except NoResultFound:
            console(
                'Could not find matching entry with ID {} in list `{}`'.format(int(options.entry), options.list_name))
            return
        except ValueError:
            db_entry = get_entry_by_title(entry_list.id, options.entry, session=session)
            if not db_entry:
                console(
                    'Could not find matching entry with title `{}` in list `{}`'.format(options.entry,
                                                                                        options.list_name))
                return
        console('Removing entry `%s` from list %s' % (db_entry.title, options.list_name))
        session.delete(db_entry)


def movie_list_purge(options):
    with Session() as session:
        try:
            entry_list = get_list_by_exact_name(options.list_name)
        except NoResultFound:
            console('Could not find entry list with name `{}`'.format(options.list_name))
            return
        console('Deleting list %s' % options.list_name)
        session.delete(entry_list)


@event('options.register')
def register_parser_arguments():
    # Common option to be used in multiple subparsers
    entry_parser = ArgumentParser(add_help=False)
    entry_parser.add_argument('-t', '--entry_title', required=True, help="Title of the entry")
    entry_parser.add_argument('-u', '--original_url', required=True, help="URL of the entry")

    global_entry_parser = ArgumentParser(add_help=False)
    global_entry_parser.add_argument('entry', help='can be entry title or ID')

    identifiers_parser = ArgumentParser(add_help=False)
    identifiers_parser.add_argument('-i', '--identifiers', metavar='<identifiers>', nargs='+',
                                    help='Can be a string or a list of string with the format imdb_id=XXX,'
                                         ' tmdb_id=XXX, etc')
    list_name_parser = ArgumentParser(add_help=False)
    list_name_parser.add_argument('-l', '--list_name', metavar='<list_name>', required=True,
                                  help='name of entry list to operate on')
    # Register subcommand
    parser = options.register_command('entry-list', do_cli, help='view and manage entry lists')
    # Set up our subparsers
    subparsers = parser.add_subparsers(title='actions', metavar='<action>', dest='list_action')
    all_parser = subparsers.add_parser('all', help='shows all existing entry lists')
    list_parser = subparsers.add_parser('list', parents=[list_name_parser], help='list entries from a list')
    show_parser = subparsers.add_parser('show', parents=[list_name_parser, global_entry_parser],
                                        help='show entry fields.')

    add_parser = subparsers.add_parser('add', parents=[identifiers_parser, list_name_parser, entry_parser],
                                       help='add an entry to a list')
    subparsers.add_parser('del', parents=[global_entry_parser, list_name_parser],
                          help='remove an entry from a list using its title')
    subparsers.add_parser('purge', parents=[list_name_parser],
                          help='removes an entire list with all of its entries. Use this with caution')
