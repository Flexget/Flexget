from __future__ import unicode_literals, division, absolute_import

from argparse import ArgumentParser, ArgumentTypeError

from sqlalchemy.orm.exc import NoResultFound

from flexget import options
from flexget.entry import Entry
from flexget.event import event
from flexget.logger import console
from flexget.manager import Session
from flexget.plugin import PluginError
from flexget.plugins.list.movie_list import get_list_by_exact_name, get_movie_lists, get_movies_by_list_id, \
    get_movie_by_title, MovieListMovie, get_db_movie_identifiers, MovieListList, SUPPORTED_IDS
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
    if name not in SUPPORTED_IDS:
        raise ArgumentTypeError(
            'Received unsupported identifier ID %s. Should be one of %s' % (identifier, ' ,'.join(SUPPORTED_IDS)))
    return {name: value}


def do_cli(manager, options):
    """Handle movie-list subcommand"""
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
    console('Existing movie lists:')
    console('-' * 20)
    for movie_list in lists:
        console(movie_list.name)


def movie_list_list(options):
    """List movie list"""
    with Session() as session:
        try:
            movie_list = get_list_by_exact_name(options.list_name)
        except NoResultFound:
            console('Could not find movie list with name {}'.format(options.list_name))
            return
        console('Movies for list {}:'.format(options.list_name))
        console('-' * 79)
        for movie in get_movies_by_list_id(movie_list.id, order_by='added', descending=True, session=session):
            _str = '{} ({}) '.format(movie.title, movie.year) if movie.year else '{} '.format(movie.title)
            _ids = '[' + ', '.join(
                '{}={}'.format(identifier.id_name, identifier.id_value) for identifier in movie.ids) + ']'
            console(_str + _ids)


def movie_list_add(options):
    with Session() as session:
        try:
            movie_list = get_list_by_exact_name(options.list_name)
        except NoResultFound:
            console('Could not find movie list with name {}, creating'.format(options.list_name))
            movie_list = MovieListList(name=options.list_name)
        session.merge(movie_list)
        title, year = split_title_year(options.movie_title)
        console('Trying to lookup movie %s title' % title)
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
            for _id in SUPPORTED_IDS:
                if entry.get(_id):
                    id_list.append({_id: entry.get(_id)})
        if id_list:
            console('Setting movie identifiers:', id_list)
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
        title, year = split_title_year(options.movie_title)
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
    parser = options.register_command('movie-list', do_cli, help='view and manage movie lists')
    # Set up our subparsers
    subparsers = parser.add_subparsers(title='actions', metavar='<action>', dest='list_action')
    subparsers.add_parser('all', help='shows all existing movie lists')
    subparsers.add_parser('list', parents=[list_name_parser], help='list movies from a list')
    subparsers.add_parser('add', parents=[list_name_parser, movie_parser, identifiers_parser],
                          help='add a movie to a list')
    subparsers.add_parser('del', parents=[list_name_parser, movie_parser],
                          help='remove a movie from a list using its title')
    subparsers.add_parser('purge', parents=[list_name_parser],
                          help='removes an entire list with all of its movies. Use this with caution')
