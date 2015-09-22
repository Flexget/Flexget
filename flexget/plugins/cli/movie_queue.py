from __future__ import unicode_literals, division, absolute_import
from argparse import ArgumentParser

from sqlalchemy.exc import OperationalError

from flexget import options
from flexget.event import event
from flexget.logger import console
from flexget.plugin import DependencyError
from flexget.utils import qualities

try:
    from flexget.plugins.filter.movie_queue import QueueError, queue_add, queue_del, queue_get, queue_forget, parse_what
except ImportError:
    raise DependencyError(issued_by='cli_movie_queue', missing='movie_queue')


def do_cli(manager, options):
    """Handle movie-queue subcommand"""

    if options.queue_action == 'list':
        queue_list(options)
        return

    # If the action affects make sure all entries are processed again next run.
    manager.config_changed()

    if options.queue_action == 'clear':
        clear()
        return

    if options.queue_action == 'del':
        try:
            what = parse_what(options.movie_name, lookup=False)
            title = queue_del(**what)
        except QueueError as e:
            console('ERROR: %s' % e.message)
        else:
            console('Removed %s from queue' % title)
        return

    if options.queue_action == 'forget':
        try:
            what = parse_what(options.movie_name, lookup=False)
            title = queue_forget(**what)
        except QueueError as e:
            console('ERROR: %s' % e.message)
        else:
            console('Forgot that %s was downloaded. Movie will be downloaded again.' % title)
        return

    if options.queue_action == 'add':
        try:
            quality = qualities.Requirements(options.quality)
        except ValueError as e:
            console('`%s` is an invalid quality requirement string: %s' % (options.quality, e.message))
            return

        # Adding to queue requires a lookup for missing information
        what = {}
        try:
            what = parse_what(options.movie_name)
        except QueueError as e:
            console('ERROR: %s' % e.message)

        if not what.get('title') or not (what.get('imdb_id') or what.get('tmdb_id')):
            console('could not determine movie')  # TODO: Rethink errors
            return

        try:
            queue_add(quality=quality, **what)
        except QueueError as e:
            console(e.message)
            if e.errno == 1:
                # This is an invalid quality error, display some more info
                # TODO: Fix this error?
                # console('Recognized qualities are %s' % ', '.join([qual.name for qual in qualities.all()]))
                console('ANY is the default and can also be used explicitly to specify that quality should be ignored.')
        except OperationalError:
            console('OperationalError')
        return


def queue_list(options):
    """List movie queue"""
    items = queue_get(downloaded=(options.type == 'downloaded'))
    if options.porcelain:
        console('%-10s %-s %-7s %-s %-37s %-s %s' % ('IMDB id', '|', 'TMDB id', '|', 'Title', '|', 'Quality'))
    else:
        console('-' * 79)
        console('%-10s %-7s %-37s %s' % ('IMDB id', 'TMDB id', 'Title', 'Quality'))
        console('-' * 79)
    for item in items:
        if options.porcelain:
            console('%-10s %-s %-7s %-s %-37s %-s %s' % (item.imdb_id, '|', item.tmdb_id, '|', item.title, '|', item.quality))
        else:
            console('%-10s %-7s %-37s %s' % (item.imdb_id, item.tmdb_id, item.title, item.quality))
    if not items:
        console('No results')
    if options.porcelain:
        pass
    else:
        console('-' * 79)


def clear():
    """Deletes waiting movies from queue"""
    items = queue_get(downloaded=False)
    console('Removing the following movies from movie queue:')
    console('-' * 79)
    for item in items:
        console(item.title)
        queue_del(title=item.title)
    if not items:
        console('No results')
    console('-' * 79)


@event('options.register')
def register_parser_arguments():
    # Common option to be used in multiple subparsers
    what_parser = ArgumentParser(add_help=False)
    what_parser.add_argument('movie_name', metavar='<movie>',
                             help='the movie (can be movie title, imdb id, or in the form `tmdb_id=XXXX`')
    # Register subcommand
    parser = options.register_command('movie-queue', do_cli, help='view and manage the movie queue')
    # Set up our subparsers
    subparsers = parser.add_subparsers(title='actions', metavar='<action>', dest='queue_action')
    list_parser = subparsers.add_parser('list', help='list movies from the queue')
    list_parser.add_argument('type', nargs='?', choices=['waiting', 'downloaded'], default='waiting',
                             help='choose to show waiting or already downloaded movies')
    list_parser.add_argument('--porcelain' , action='store_true', help='make the output parseable')
    add_parser = subparsers.add_parser('add', parents=[what_parser], help='add a movie to the queue')
    add_parser.add_argument('quality', metavar='<quality>', default='ANY', nargs='?',
                            help='the quality requirements for getting this movie (default: %(default)s)')
    subparsers.add_parser('del', parents=[what_parser], help='remove a movie from the queue')
    subparsers.add_parser('forget', parents=[what_parser], help='remove the downloaded flag from a movie')
    subparsers.add_parser('clear', help='remove all un-downloaded movies from the queue')
