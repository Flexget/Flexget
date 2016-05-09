from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

from flexget import options
from flexget.event import event
from flexget.logger import console
from flexget.plugins.filter import seen
from flexget.utils.database import with_session
from flexget.utils.imdb import is_imdb_url, extract_id


def do_cli(manager, options):
    if options.seen_action == 'forget':
        seen_forget(manager, options)
    elif options.seen_action == 'add':
        seen_add(options)
    elif options.seen_action == 'search':
        seen_search(options)


def seen_forget(manager, options):
    forget_name = options.forget_value
    if is_imdb_url(forget_name):
        imdb_id = extract_id(forget_name)
        if imdb_id:
            forget_name = imdb_id

    count, fcount = seen.forget(forget_name)
    console('Removed %s titles (%s fields)' % (count, fcount))
    manager.config_changed()


def seen_add(options):
    seen_name = options.add_value
    if is_imdb_url(seen_name):
        imdb_id = extract_id(seen_name)
        if imdb_id:
            seen_name = imdb_id
    seen.add(seen_name, 'cli_add', {'cli_add': seen_name})
    console('Added %s as seen. This will affect all tasks.' % seen_name)


@with_session
def seen_search(options, session=None):
    search_term = '%' + options.search_term + '%'
    seen_entries = seen.search(value=search_term, status=None, session=session)
    for se in seen_entries.all():
        console('ID: %s Name: %s Task: %s Added: %s' % (se.id, se.title, se.task, se.added.strftime('%c')))
        for sf in se.fields:
            console(' %s: %s' % (sf.field, sf.value))
        console('')
    if not seen_entries:
        console('No results')


@event('options.register')
def register_parser_arguments():
    parser = options.register_command('seen', do_cli, help='view or forget entries remembered by the seen plugin')
    subparsers = parser.add_subparsers(dest='seen_action', metavar='<action>')
    forget_parser = subparsers.add_parser('forget', help='forget entry or entire task from seen plugin database')
    forget_parser.add_argument('forget_value', metavar='<value>',
                               help='title or url of entry to forget, or name of task to forget')
    add_parser = subparsers.add_parser('add', help='add a title or url to the seen database')
    add_parser.add_argument('add_value', metavar='<value>', help='the title or url to add')
    search_parser = subparsers.add_parser('search', help='search text from the seen database')
    search_parser.add_argument('search_term', metavar='<search term>')
