from __future__ import unicode_literals, division, absolute_import

from argparse import ArgumentParser, ArgumentTypeError

from sqlalchemy.orm.exc import NoResultFound

from flexget import options
from flexget.event import event
from flexget.logger import console
from flexget.manager import Session
from flexget.plugins.list.movie_list import get_list_by_exact_name, get_movie_lists, get_movies_by_list_id, \
    get_movie_by_title, MovieListMovie, get_db_movie_identifiers, MovieListList, SUPPORTED_IDS
from flexget.utils.tools import split_title_year


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
            session.add(movie_list)
        session.merge(movie_list)
        title, year = split_title_year(options.movie_title)
        movie_exist = get_movie_by_title(list_id=movie_list.id, title=title, session=session)
        if movie_exist:
            console("Movie with the title {} already exist with list {}. Will replace identifiers if given".format(
                title, movie_list.name))
            output = 'Successfully updated movie {} to movie list {} '.format(title, movie_list.name)
        else:
            console("Adding movie with title {} to list {}".format(title, movie_list.name))
            movie_exist = MovieListMovie(title=title, year=year, list_id=movie_list.id)
            session.add(movie_exist)
            output = 'Successfully added movie {} to movie list {} '.format(title, movie_list.name)
        if options.identifiers:
            console('Adding identifiers {} to movie {}'.format(options.identifiers, title))
            movie_exist.ids = get_db_movie_identifiers(identifier_list=options.identifiers, session=session)
        console(output)


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
    movie_parser.add_argument('-t', '--movie_title', required=True, help="Title of the movie")

    identifiers_parser = ArgumentParser(add_help=False)
    identifiers_parser.add_argument('-i', '--identifiers', metavar='<identifiers>', nargs='+',
                                    type=movie_list_keyword_type,
                                    help='Can be a string or a list of string with the format imdb_id=XXX,'
                                         ' tmdb_id=XXX, etc')
    list_name_parser = ArgumentParser(add_help=False)
    list_name_parser.add_argument('-l', '--list_name', metavar='<list_name>', required=True,
                                  help='name of movie list to operate on')
    # Register subcommand
    parser = options.register_command('movie-list', do_cli, help='view and manage movie lists')
    # Set up our subparsers
    subparsers = parser.add_subparsers(title='actions', metavar='<action>', dest='list_action')
    all_parser = subparsers.add_parser('all', help='shows all existing movie lists')
    list_parser = subparsers.add_parser('list', parents=[list_name_parser], help='list movies from a list')
    add_parser = subparsers.add_parser('add', parents=[identifiers_parser, list_name_parser, movie_parser],
                                       help='add a movie to a list')
    subparsers.add_parser('del', parents=[movie_parser, list_name_parser],
                          help='remove a movie from a list using its title')
    subparsers.add_parser('purge', parents=[list_name_parser],
                          help='removes an entire list with all of its movies. Use this with caution')
