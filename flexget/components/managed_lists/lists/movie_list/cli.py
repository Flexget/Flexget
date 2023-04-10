from argparse import ArgumentParser, ArgumentTypeError

from sqlalchemy.orm.exc import NoResultFound

from flexget import options, plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.manager import Session
from flexget.plugin import DependencyError, PluginError
from flexget.terminal import TerminalTable, console, table_parser
from flexget.utils.tools import split_title_year

from . import db
from .movie_list import MovieListBase


def lookup_movie(title, session, identifiers=None):
    try:
        imdb_lookup = plugin.get('imdb_lookup', 'movie_list').lookup
    except DependencyError:
        imdb_lookup = None

    try:
        tmdb_lookup = plugin.get('tmdb_lookup', 'movie_list').lookup
    except DependencyError:
        tmdb_lookup = None

    if not (imdb_lookup or tmdb_lookup):
        return

    entry = Entry(title=title)
    if identifiers:
        for identifier in identifiers:
            for key, value in identifier.items():
                entry[key] = value
    try:
        imdb_lookup(entry, session=session)
    # IMDB lookup raises PluginError instead of the normal ValueError
    except PluginError:
        tmdb_lookup(entry)

    # Return only if lookup was successful
    if entry.get('movie_name'):
        return entry
    return


def movie_list_keyword_type(identifier):
    if identifier.count('=') != 1:
        raise ArgumentTypeError(
            'Received identifier in wrong format: {}, '
            ' should be in keyword format like `imdb_id=tt1234567`'.format(identifier)
        )
    name, value = identifier.split('=', 2)
    if name not in MovieListBase().supported_ids:
        raise ArgumentTypeError(
            'Received unsupported identifier ID {}. Should be one of {}'.format(
                identifier, ' ,'.join(MovieListBase().supported_ids)
            )
        )
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
    """Show all movie lists"""
    lists = db.get_movie_lists()
    header = ['#', 'List Name']
    table = TerminalTable(*header, table_type=options.table_type)
    for movie_list in lists:
        table.add_row(str(movie_list.id), movie_list.name)

    console(table)


def movie_list_list(options):
    """List movie list"""
    with Session() as session:
        try:
            movie_list = db.get_list_by_exact_name(options.list_name)
        except NoResultFound:
            console(f'Could not find movie list with name {options.list_name}')
            return
    header = ['#', 'Movie Name', 'Movie year']
    header += db.MovieListBase().supported_ids
    movies = db.get_movies_by_list_id(
        movie_list.id, order_by='added', descending=True, session=session
    )
    title = f'{len(movies)} Movies in movie list: `{options.list_name}`'
    table = TerminalTable(*header, table_type=options.table_type, title=title)
    for movie in movies:
        movie_row = [str(movie.id), movie.title, str(movie.year) or '']
        for identifier in db.MovieListBase().supported_ids:
            movie_row.append(str(movie.identifiers.get(identifier, '')))
        table.add_row(*movie_row)
    console(table)


def movie_list_add(options):
    with Session() as session:
        try:
            movie_list = db.get_list_by_exact_name(options.list_name, session=session)
        except NoResultFound:
            console(f'Could not find movie list with name {options.list_name}, creating')
            movie_list = db.MovieListList(name=options.list_name)
            session.add(movie_list)
            session.commit()

        title, year = split_title_year(options.movie_title)
        console(f'Trying to lookup movie title: `{title}`')
        movie_lookup = lookup_movie(title=title, session=session, identifiers=options.identifiers)
        if not movie_lookup:
            console(f'ERROR: movie lookup failed for movie {options.movie_title}, aborting')
            return

        title = movie_lookup['movie_name']
        movie = db.get_movie_by_title_and_year(
            list_id=movie_list.id, title=title, year=year, session=session
        )
        if not movie:
            console(f"Adding movie with title {title} to list {movie_list.name}")
            movie = db.MovieListMovie(title=title, year=year, list_id=movie_list.id)
        else:
            console(f"Movie with title {title} already exist in list {movie_list.name}")

        id_list = []
        if options.identifiers:
            id_list = options.identifiers
        else:
            for _id in db.MovieListBase().supported_ids:
                if movie_lookup.get(_id):
                    id_list.append({_id: movie_lookup.get(_id)})
        if id_list:
            console('Setting movie identifiers:')
            for ident in id_list:
                for key in ident:
                    console(f'{key}: {ident[key]}')
            movie.ids = db.get_db_movie_identifiers(identifier_list=id_list, session=session)
        session.merge(movie)
        console(f'Successfully added movie {title} to movie list {movie_list.name} ')


def movie_list_del(options):
    with Session() as session:
        try:
            movie_list = db.get_list_by_exact_name(options.list_name)
        except NoResultFound:
            console(f'Could not find movie list with name {options.list_name}')
            return

        try:
            movie_exist = db.get_movie_by_id(
                list_id=movie_list.id, movie_id=int(options.movie), session=session
            )
        except NoResultFound:
            console(
                'Could not find movie with ID {} in list `{}`'.format(
                    int(options.movie), options.list_name
                )
            )
            return
        except ValueError:
            title, year = split_title_year(options.movie)
            movie_exist = db.get_movie_by_title_and_year(
                list_id=movie_list.id, title=title, year=year, session=session
            )
        if not movie_exist:
            console(
                'Could not find movie with title {} in list {}'.format(
                    options.movie, options.list_name
                )
            )
            return
        else:
            console(f'Removing movie {movie_exist.title} from list {options.list_name}')
            session.delete(movie_exist)


def movie_list_purge(options):
    with Session() as session:
        try:
            movie_list = db.get_list_by_exact_name(options.list_name)
        except NoResultFound:
            console(f'Could not find movie list with name {options.list_name}')
            return
        console(f'Deleting list {options.list_name}')
        session.delete(movie_list)


@event('options.register')
def register_parser_arguments():
    # Common option to be used in multiple subparsers
    movie_parser = ArgumentParser(add_help=False)
    movie_parser.add_argument('movie_title', metavar='<MOVIE TITLE>', help="Title of the movie")

    name_or_id_parser = ArgumentParser(add_help=False)
    name_or_id_parser.add_argument(
        'movie', metavar='<NAME or ID>', help="Title or ID of the movie"
    )

    identifiers_parser = ArgumentParser(add_help=False)
    identifiers_parser.add_argument(
        '-i',
        '--identifiers',
        metavar='<identifiers>',
        nargs='+',
        type=movie_list_keyword_type,
        help='Can be a string or a list of string with the format imdb_id=XXX,'
        ' tmdb_id=XXX, etc',
    )
    list_name_parser = ArgumentParser(add_help=False)
    list_name_parser.add_argument(
        'list_name',
        nargs='?',
        metavar='<LIST NAME>',
        default='movies',
        help='Name of movie list to operate on (Default is \'movies\')',
    )
    # Register subcommand
    parser = options.register_command('movie-list', do_cli, help='View and manage movie lists')
    # Set up our subparsers
    subparsers = parser.add_subparsers(title='actions', metavar='<action>', dest='list_action')
    subparsers.add_parser('all', parents=[table_parser], help='Shows all existing movie lists')
    subparsers.add_parser(
        'list', parents=[list_name_parser, table_parser], help='List movies from a list'
    )
    subparsers.add_parser(
        'add',
        parents=[list_name_parser, movie_parser, identifiers_parser],
        help='Add a movie to a list',
    )
    subparsers.add_parser(
        'del',
        parents=[list_name_parser, name_or_id_parser],
        help='Remove a movie from a list using its title or ID',
    )
    subparsers.add_parser(
        'purge',
        parents=[list_name_parser],
        help='Removes an entire list with all of its movies. Use this with caution',
    )
