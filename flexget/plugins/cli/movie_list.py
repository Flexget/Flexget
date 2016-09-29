from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

from argparse import ArgumentParser, ArgumentTypeError

from sqlalchemy.orm.exc import NoResultFound

from flexget import options
from flexget.entry import Entry
from flexget.event import event
from flexget.manager import Session
from flexget.terminal import TerminalTable, TerminalTableError, table_parser, console
from flexget.plugin import PluginError
from flexget.plugins.list.movie_list import get_list_by_exact_name, get_movie_lists, get_movies_by_list_id, \
    get_movie_by_title, MovieListMovie, get_db_movie_identifiers, MovieListList, MovieListBase
from flexget.plugins.metainfo.imdb_lookup import ImdbLookup
from flexget.plugins.metainfo.tmdb_lookup import PluginTmdbLookup
from flexget.utils.tools import split_title_year

imdb_lookup = ImdbLookup().lookup
tmdb_lookup = PluginTmdbLookup().lookup


def lookup_movie(title, session, identifiers=None):
    entry = Entry(title=title)
    if identifiers:
        for identifier in identifiers:
            for key, value in identifier.items():
                entry[key] = value
    try:
        imdb_lookup(entry, session=session)
    except PluginError:
        tmdb_lookup(entry)
    if entry.get('movie_name'):
        return entry


def movie_list_keyword_type(identifier):
    if identifier.count('=') != 1:
        raise ArgumentTypeError('Received identifier in wrong format: %s, '
                                ' should be in keyword format like `imdb_id=tt1234567`' % identifier)
    name, value = identifier.split('=', 2)
    if name not in MovieListBase().supported_ids:
        raise ArgumentTypeError(
            'Received unsupported identifier ID %s. Should be one of %s' % (
                identifier, ' ,'.join(MovieListBase().supported_ids)))
    return {name: value}


def do_cli(manager, options):
    """Handle movie-list subcommand"""

    # Handle globally setting value for word wrap method
    if options.list_action == 'all':
        movie_list_lists(options)
        return

    if options.list_action == 'list':
        movie_list_list(options)
        return

    if options.list_action == 'add':
        movie_list_add(options)
        return

    if options.list_action == 'del':
        movie_list_del(options)
        return

    if options.list_action == 'purge':
        movie_list_purge(options)
        return


def movie_list_lists(options):
    """ Show all movie lists """
    lists = get_movie_lists()
    header = ['#', 'List Name']
    table_data = [header]
    for movie_list in lists:
        table_data.append([movie_list.id, movie_list.name])
    table = TerminalTable(options.table_type, table_data)
    try:
        console(table.output)
    except TerminalTableError as e:
        console('ERROR: %s' % str(e))


def movie_list_list(options):
    """List movie list"""
    with Session() as session:
        try:
            movie_list = get_list_by_exact_name(options.list_name)
        except NoResultFound:
            console('Could not find movie list with name {}'.format(options.list_name))
            return
    header = ['Movie Name', 'Movie year']
    header += MovieListBase().supported_ids
    table_data = [header]
    movies = get_movies_by_list_id(movie_list.id, order_by='added', descending=True, session=session)
    for movie in movies:
        movie_row = [movie.title, movie.year or '']
        for identifier in MovieListBase().supported_ids:
            movie_row.append(movie.identifiers.get(identifier, ''))
        table_data.append(movie_row)
    title = '{} Movies in movie list: `{}`'.format(len(movies), options.list_name)
    table = TerminalTable(options.table_type, table_data, title, drop_columns=[5, 2, 4])
    try:
        console(table.output)
    except TerminalTableError as e:
        console('ERROR: %s' % str(e))


def movie_list_add(options):
    with Session() as session:
        try:
            movie_list = get_list_by_exact_name(options.list_name, session=session)
        except NoResultFound:
            console('Could not find movie list with name {}, creating'.format(options.list_name))
            movie_list = MovieListList(name=options.list_name)
            session.add(movie_list)
            session.commit()
        title, year = split_title_year(options.movie_title)
        console('Trying to lookup movie title: `{}`'.format(title))
        entry = lookup_movie(title=title, session=session, identifiers=options.identifiers)
        if not entry:
            console('movie lookup failed for movie %s, aborting')
            return
        title = entry['movie_name']
        movie = get_movie_by_title(list_id=movie_list.id, title=title, session=session)
        if not movie:
            console("Adding movie with title {} to list {}".format(title, movie_list.name))
            movie = MovieListMovie(title=entry['movie_name'], year=year, list_id=movie_list.id)
        else:
            console("Movie with title {} already exist in list {}".format(title, movie_list.name))

        id_list = []
        if options.identifiers:
            id_list = options.identifiers
        else:
            for _id in MovieListBase().supported_ids:
                if entry.get(_id):
                    id_list.append({_id: entry.get(_id)})
        if id_list:
            console('Setting movie identifiers:')
            for ident in id_list:
                for key in ident:
                    console('{}: {}'.format(key, ident[key]))
            movie.ids = get_db_movie_identifiers(identifier_list=id_list, session=session)
        session.merge(movie)
        console('Successfully added movie {} to movie list {} '.format(title, movie_list.name))


def movie_list_del(options):
    with Session() as session:
        try:
            movie_list = get_list_by_exact_name(options.list_name)
        except NoResultFound:
            console('Could not find movie list with name {}'.format(options.list_name))
            return
        title = split_title_year(options.movie_title)[0]
        movie_exist = get_movie_by_title(list_id=movie_list.id, title=title, session=session)
        if movie_exist:
            console('Removing movie %s from list %s' % (options.movie_title, options.list_name))
            session.delete(movie_exist)
        else:
            console('Could not find movie with title %s in list %s' % (options.movie_title, options.list_name))
            return


def movie_list_purge(options):
    with Session() as session:
        try:
            movie_list = get_list_by_exact_name(options.list_name)
        except NoResultFound:
            console('Could not find movie list with name {}'.format(options.list_name))
            return
        console('Deleting list %s' % options.list_name)
        session.delete(movie_list)


@event('options.register')
def register_parser_arguments():
    # Common option to be used in multiple subparsers
    movie_parser = ArgumentParser(add_help=False)
    movie_parser.add_argument('movie_title', help="Title of the movie")

    identifiers_parser = ArgumentParser(add_help=False)
    identifiers_parser.add_argument('-i', '--identifiers', metavar='<identifiers>', nargs='+',
                                    type=movie_list_keyword_type,
                                    help='Can be a string or a list of string with the format imdb_id=XXX,'
                                         ' tmdb_id=XXX, etc')
    list_name_parser = ArgumentParser(add_help=False)
    list_name_parser.add_argument('list_name', nargs='?', default='movies', help='Name of movie list to operate on')
    # Register subcommand
    parser = options.register_command('movie-list', do_cli, help='View and manage movie lists')
    # Set up our subparsers
    subparsers = parser.add_subparsers(title='actions', metavar='<action>', dest='list_action')
    subparsers.add_parser('all', parents=[table_parser], help='Shows all existing movie lists')
    subparsers.add_parser('list', parents=[list_name_parser, table_parser], help='List movies from a list')
    subparsers.add_parser('add', parents=[list_name_parser, movie_parser, identifiers_parser],
                          help='Add a movie to a list')
    subparsers.add_parser('del', parents=[list_name_parser, movie_parser],
                          help='Remove a movie from a list using its title')
    subparsers.add_parser('purge', parents=[list_name_parser],
                          help='Removes an entire list with all of its movies. Use this with caution')
