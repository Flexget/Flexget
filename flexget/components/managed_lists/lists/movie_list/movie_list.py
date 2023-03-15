from collections.abc import MutableSet

from loguru import logger
from sqlalchemy import func
from sqlalchemy.sql.elements import and_

from flexget import plugin
from flexget.db_schema import with_session
from flexget.event import event
from flexget.manager import Session
from flexget.utils.tools import split_title_year

from . import db

try:
    # NOTE: Importing other plugins is discouraged!
    from flexget.components.parsing.parsers import parser_common as plugin_parser_common
except ImportError:
    raise plugin.DependencyError(issued_by=__name__, missing='parser_common')

logger = logger.bind(name='movie_list')


class MovieListBase:
    """
    Class that contains helper methods for movie list as well as plugins that use it,
    such as API and CLI.
    """

    @property
    def supported_ids(self):
        # Return a list of supported series identifier as registered via their plugins
        return [
            p.instance.movie_identifier for p in plugin.get_plugins(interface='movie_metainfo')
        ]


class MovieList(MutableSet):
    def _db_list(self, session):
        return (
            session.query(db.MovieListList).filter(db.MovieListList.name == self.list_name).first()
        )

    def _from_iterable(self, it):
        # TODO: is this the right answer? the returned object won't have our custom __contains__ logic
        return set(it)

    @with_session
    def __init__(self, config, session=None):
        if not isinstance(config, dict):
            config = {'list_name': config}
        config.setdefault('strip_year', False)
        self.list_name = config.get('list_name')
        self.strip_year = config.get('strip_year')

        db_list = self._db_list(session)
        if not db_list:
            session.add(db.MovieListList(name=self.list_name))

    def __iter__(self):
        with Session() as session:
            return iter(
                [movie.to_entry(self.strip_year) for movie in self._db_list(session).movies]
            )

    def __len__(self):
        with Session() as session:
            return len(self._db_list(session).movies)

    def add(self, entry):
        with Session() as session:
            # Check if this is already in the list, refresh info if so
            db_list = self._db_list(session=session)
            db_movie = self._find_entry(entry, session=session)
            # Just delete and re-create to refresh
            if db_movie:
                session.delete(db_movie)
            db_movie = db.MovieListMovie()
            if 'movie_name' in entry:
                db_movie.title, db_movie.year = entry['movie_name'], entry.get('movie_year')
            else:
                db_movie.title, db_movie.year = split_title_year(entry['title'])
            for id_name in MovieListBase().supported_ids:
                if id_name in entry:
                    db_movie.ids.append(db.MovieListID(id_name=id_name, id_value=entry[id_name]))
            logger.debug('adding entry {}', entry)
            db_list.movies.append(db_movie)
            session.commit()
            return db_movie.to_entry()

    def discard(self, entry):
        with Session() as session:
            db_movie = self._find_entry(entry, session=session)
            if db_movie:
                logger.debug('deleting movie {}', db_movie)
                session.delete(db_movie)

    def __contains__(self, entry):
        return self._find_entry(entry) is not None

    @with_session
    def _find_entry(self, entry, session=None):
        """Finds `MovieListMovie` corresponding to this entry, if it exists."""
        # Match by supported IDs
        for id_name in MovieListBase().supported_ids:
            if entry.get(id_name):
                logger.debug('trying to match movie based off id {}: {}', id_name, entry[id_name])
                res = (
                    self._db_list(session)
                    .movies.join(db.MovieListMovie.ids)
                    .filter(
                        and_(
                            db.MovieListID.id_name == id_name,
                            db.MovieListID.id_value == entry[id_name],
                        )
                    )
                    .first()
                )
                if res:
                    logger.debug('found movie {}', res)
                    return res
        # Fall back to title/year match
        if not entry.get('movie_name'):
            self._parse_title(entry)
        if entry.get('movie_name'):
            name = entry['movie_name']
            year = entry.get('movie_year') if entry.get('movie_year') else None
        else:
            logger.warning('Could not get a movie name, skipping')
            return
        logger.debug('trying to match movie based of name: {} and year: {}', name, year)
        res = (
            self._db_list(session)
            .movies.filter(func.lower(db.MovieListMovie.title) == name.lower())
            .filter(db.MovieListMovie.year == year)
            .first()
        )
        if res:
            logger.debug('found movie {}', res)
        return res

    @staticmethod
    def _parse_title(entry):
        parser = plugin.get('parsing', 'movie_list').parse_movie(data=entry['title'])
        if parser and parser.valid:
            parser.name = plugin_parser_common.normalize_name(
                plugin_parser_common.remove_dirt(parser.name)
            )
            entry.update(parser.fields)

    @property
    def immutable(self):
        return False

    @property
    def online(self):
        """
        Set the online status of the plugin, online plugin should be treated
        differently in certain situations, like test mode
        """
        return False

    @with_session
    def get(self, entry, session):
        match = self._find_entry(entry=entry, session=session)
        return match.to_entry() if match else None


class PluginMovieList:
    """Remove all accepted elements from your trakt.tv watchlist/library/seen or custom list."""

    schema = {
        'oneOf': [
            {'type': 'string'},
            {
                'type': 'object',
                'properties': {'list_name': {'type': 'string'}, 'strip_year': {'type': 'boolean'}},
                'required': ['list_name'],
                'additionalProperties': False,
            },
        ]
    }

    @staticmethod
    def get_list(config):
        return MovieList(config)

    def on_task_input(self, task, config):
        return list(MovieList(config))


@event('plugin.register')
def register_plugin():
    plugin.register(PluginMovieList, 'movie_list', api_ver=2, interfaces=['task', 'list'])
