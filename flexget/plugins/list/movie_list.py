from __future__ import unicode_literals, division, absolute_import
import logging
from collections import MutableSet

from sqlalchemy import Column, Unicode, Integer, ForeignKey
from sqlalchemy.orm import relationship

from flexget import plugin
from flexget.db_schema import versioned_base, with_session
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.tools import split_title_year

log = logging.getLogger('movie_list')
Base = versioned_base('trakt_list', 0)

SUPPORTED_IDS = ['imdb_id', 'trakt_movie_id', 'tmdb_id']


class MovieListList(Base):
    __tablename__ = 'movie_list_lists'
    id = Column(Integer, primary_key=True)
    name = Column(Unicode, unique=True)
    movies = relationship('MovieListMovie', backref='list', cascade='all, delete, delete-orphan')


class MovieListMovie(Base):
    __tablename__ = 'movie_list_movies'
    id = Column(Integer, primary_key=True)
    title = Column(Unicode)
    year = Column(Integer)
    list_id = Column(Integer, ForeignKey(MovieListList.id), nullable=False)
    ids = relationship('MovieListID', backref='movie', cascade='all, delete, delete-orphan')

    def to_entry(self):
        entry = Entry()
        entry['title'] = entry['movie_name'] = self.title
        if self.year:
            entry['title'] += ' (%d)' % self.year
            entry['movie_year'] = self.year
        for id in self.ids:
            entry[id.id_name] = id.id_value
        return entry


class MovieListID(Base):
    __tablename__ = 'movie_list_ids'
    id = Column(Integer, primary_key=True)
    id_name = Column(Unicode)
    id_value = Column(Unicode)
    movie_id = Column(Integer, ForeignKey(MovieListMovie.id))


class MovieList(MutableSet):
    def _db_list(self, session):
        return session.query(MovieListList).filter(MovieListList.name == self.config).first()

    @with_session
    def __init__(self, config, session=None):
        self.config = config
        db_list = self._db_list(session)
        if not db_list:
            session.add(MovieListList(name=self.config))

    @with_session
    def __iter__(self, session=None):
        return (movie.to_entry() for movie in self._db_list(session).movies)

    @with_session
    def __len__(self, session=None):
        return len(self._db_list(session).movies)

    @with_session
    def add(self, entry, session=None):
        # Check if this is already in the list, refresh info if so
        db_list = self._db_list(session=session)
        db_movie = self._find_entry(entry, session=session)
        # Just delete and re-create to refresh
        if db_movie:
            session.delete(db_movie)
        db_movie = MovieListMovie()
        if 'movie_name' in entry:
            db_movie.title, db_movie.year = entry['movie_name'], entry.get('movie_year')
        else:
            db_movie.title, db_movie.year = split_title_year(entry['title'])
        for id_name in SUPPORTED_IDS:
            if id_name in entry:
                db_movie.ids.append(MovieListID(id_name=id_name, id_value=entry[id_name]))
        db_list.movies.append(db_movie)

    @with_session
    def discard(self, entry, session=None):
        db_movie = self._find_entry(entry, session)
        if db_movie:
            session.delete(db_movie)

    def __contains__(self, entry):
        return self._find_entry(entry) is not None

    @with_session
    def _find_entry(self, entry, session=None):
        """Finds `MovieListMovie` corresponding to this entry, if it exists."""
        for id_name in SUPPORTED_IDS:
            if id_name in entry:
                # TODO: Make this real
                res = (session.query(MovieListID).filter(inourlist)
                                                 .filter(MovieListID.id_name == id_name)
                                                 .filter(MovieListID.id_value == entry[id_name]).first())
                if res:
                    return res.movie
        # Fall back to title/year match
        if 'movie_name' in entry and 'movie_year' in entry:
            name, year = entry['movie_name'], entry['movie_year']
        else:
            name, year = split_title_year(entry['title'])
        res = (session.quey(MovieListMovie).filter(inourlist)
                                            .filter(MovieListMovie.title == name)
                                            .filter(MovieListMovie.year == year).first())
        return res


class PluginMovieList(object):
    """Remove all accepted elements from your trakt.tv watchlist/library/seen or custom list."""
    schema = {'type': 'string'}

    @staticmethod
    def get_list(config):
        return MovieList(config)

    def on_task_input(self, task, config):
        return list(MovieList(config))


@event('plugin.register')
def register_plugin():
    plugin.register(PluginMovieList, 'movie_list', api_ver=2, groups=['list'])
