from __future__ import unicode_literals, division, absolute_import

from argparse import ArgumentParser

from sqlalchemy.orm.exc import NoResultFound

from flexget import options
from flexget.event import event
from flexget.logger import console
from flexget.plugin import DependencyError
from flexget.utils.database import with_session
from flexget.utils.tools import split_title_year

try:
    from flexget.plugins.list.movie_list import get_list_by_exact_name, get_movie_lists, get_movies_by_list_id, \
        get_movie_by_title, MovieListMovie, get_db_movie_identifiers, MovieListList
except ImportError:
    raise DependencyError(issued_by='cli_movie_list', missing='movie_list')


def parse_identifier(identifier_string):
    if identifier_string.count('=') != 1:
        return
    name, value = identifier_string.split('=', 2)
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
    for list in lists:
        console(list.name)


@with_session
def movie_list_list(options, session=None):
    """List movie list"""
    try:
        list = get_list_by_exact_name(options.list_name)
    except NoResultFound:
        console('Could not find movie list with name {}'.format(options.list_name))
        return
    console('Movies for list {}:'.format(options.list_name))
    console('-' * 79)
    for movie in get_movies_by_list_id(list.id, order_by='added', descending=True, session=session):
        _str = '{} ({}) '.format(movie.title, movie.year) if movie.year else '{} '.format(movie.title)
        _ids = '[' + ', '.join(
            '{}={}'.format(identifier.id_name, identifier.id_value) for identifier in movie.ids) + ']'
        console(_str + _ids)


@with_session
def movie_list_add(options, session=None):
    try:
        list = get_list_by_exact_name(options.list_name)
    except NoResultFound:
        console('Could not find movie list with name {}, creating'.format(options.list_name))
        list = MovieListList(name=options.list_name)
        session.add(list)
        session.commit()
    title, year = split_title_year(options.movie_title)
    movie_exist = get_movie_by_title(list_id=list.id, title=title, session=session)
    if movie_exist:
        console("Movie with the title {} already exist with list {}. Will replace identifiers if given".format(
            title, list.name))
        output = 'Successfully updated movie {} to movie list {} '.format(title, list.name)
    else:
        console("Adding movie with title {} to list {}".format(title, list.name))
        movie_exist = MovieListMovie(title=title, year=year, list_id=list.id)
        session.add(movie_exist)
        output = 'Successfully added movie {} to movie list {} '.format(title, list.name)
    if options.identifiers:
        identifiers = [parse_identifier(identifier) for identifier in options.identifiers if options.identifiers]
        console('Adding identifiers {} to movie {}'.format(identifiers, title))
        movie_exist.ids = get_db_movie_identifiers(identifier_list=identifiers, session=session)
    console(output)


@with_session
def movie_list_del(options, session=None):
    try:
        list = get_list_by_exact_name(options.list_name)
    except NoResultFound:
        console('Could not find movie list with name {}'.format(options.list_name))
        return
    title, year = split_title_year(options.movie_title)
    movie_exist = get_movie_by_title(list_id=list.id, title=title, session=session)
    if movie_exist:
        console('Removing movie %s from list %s' % (options.movie_title, options.list_name))
        session.delete(movie_exist)
    else:
        console('Could not find movie with title %s in list %s' % (options.movie_title, options.list_name))
        return


@with_session
def movie_list_purge(options, session=None):
    try:
        list = get_list_by_exact_name(options.list_name)
    except NoResultFound:
        console('Could not find movie list with name {}'.format(options.list_name))
        return
    console('Deleting list %s' % options.list_name)
    session.delete(list)


@event('options.register')
def register_parser_arguments():
    # Common option to be used in multiple subparsers
    movie_parser = ArgumentParser(add_help=False)
    movie_parser.add_argument('-t', '--movie_title', required=True, help="Title of the movie")

    identifiers_parser = ArgumentParser(add_help=False)
    identifiers_parser.add_argument('-i', '--identifiers', metavar='<identifiers>', nargs='+',
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
