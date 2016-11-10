from __future__ import unicode_literals, division, absolute_import

import logging
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from collections import MutableSet
from datetime import datetime

from sqlalchemy import Column, Unicode, Integer, ForeignKey, func, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql.elements import and_

from flexget import plugin
from flexget.db_schema import versioned_base, with_session
from flexget.entry import Entry
from flexget.event import event
from flexget.manager import Session
from flexget.plugin import get_plugin_by_name
from flexget.plugins.parsers.parser_common import normalize_name, remove_dirt
from flexget.utils.tools import split_title_year

log = logging.getLogger('movie_list')
Base = versioned_base('movie_list', 0)


class MovieListBase(object):
    """
    Class that contains helper methods for movie list as well as plugins that use it,
    such as API and CLI.
    """

    @property
    def supported_ids(self):
        # Return a list of supported series identifier as registered via their plugins
        return [p.instance.movie_identifier for p in plugin.get_plugins(group='movie_metainfo')]


class MovieListList(Base):
    __tablename__ = 'movie_list_lists'
    id = Column(Integer, primary_key=True)
    name = Column(Unicode, unique=True)
    added = Column(DateTime, default=datetime.now)
    movies = relationship('MovieListMovie', backref='list', cascade='all, delete, delete-orphan', lazy='dynamic')

    def __repr__(self):
        return '<MovieListList,name={}id={}>'.format(self.name, self.id)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'added_on': self.added
        }


class MovieListMovie(Base):
    __tablename__ = 'movie_list_movies'
    id = Column(Integer, primary_key=True)
    added = Column(DateTime, default=datetime.now)
    title = Column(Unicode)
    year = Column(Integer)
    list_id = Column(Integer, ForeignKey(MovieListList.id), nullable=False)
    ids = relationship('MovieListID', backref='movie', cascade='all, delete, delete-orphan')

    def __repr__(self):
        return '<MovieListMovie title=%s,year=%s,list_id=%d>' % (self.title, self.year, self.list_id)

    def to_entry(self, strip_year=False):
        entry = Entry()
        entry['title'] = entry['movie_name'] = self.title
        entry['url'] = 'mock://localhost/movie_list/%d' % self.id
        entry['added'] = self.added
        if self.year:
            if strip_year is False:
                entry['title'] += ' (%d)' % self.year
            entry['movie_year'] = self.year
        for movie_list_id in self.ids:
            entry[movie_list_id.id_name] = movie_list_id.id_value
        return entry

    def to_dict(self):
        return {
            'id': self.id,
            'added_on': self.added,
            'title': self.title,
            'year': self.year,
            'list_id': self.list_id,
            'movies_list_ids': [movie_list_id.to_dict() for movie_list_id in self.ids]
        }

    @property
    def identifiers(self):
        """ Return a dict of movie identifiers """
        return {identifier.id_name: identifier.id_value for identifier in self.ids}


class MovieListID(Base):
    __tablename__ = 'movie_list_ids'
    id = Column(Integer, primary_key=True)
    added = Column(DateTime, default=datetime.now)
    id_name = Column(Unicode)
    id_value = Column(Unicode)
    movie_id = Column(Integer, ForeignKey(MovieListMovie.id))

    def __repr__(self):
        return '<MovieListID id_name=%s,id_value=%s,movie_id=%d>' % (self.id_name, self.id_value, self.movie_id)

    def to_dict(self):
        return {
            'id': self.id,
            'added_on': self.added,
            'id_name': self.id_name,
            'id_value': self.id_value,
            'movie_id': self.movie_id
        }


class MovieList(MutableSet):
    def _db_list(self, session):
        return session.query(MovieListList).filter(MovieListList.name == self.list_name).first()

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
            session.add(MovieListList(name=self.list_name))

    def __iter__(self):
        with Session() as session:
            return iter([movie.to_entry(self.strip_year) for movie in self._db_list(session).movies])

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
            db_movie = MovieListMovie()
            if 'movie_name' in entry:
                db_movie.title, db_movie.year = entry['movie_name'], entry.get('movie_year')
            else:
                db_movie.title, db_movie.year = split_title_year(entry['title'])
            for id_name in MovieListBase().supported_ids:
                if id_name in entry:
                    db_movie.ids.append(MovieListID(id_name=id_name, id_value=entry[id_name]))
            log.debug('adding entry %s', entry)
            db_list.movies.append(db_movie)
            session.commit()
            return db_movie.to_entry()

    def discard(self, entry):
        with Session() as session:
            db_movie = self._find_entry(entry, session=session)
            if db_movie:
                log.debug('deleting movie %s', db_movie)
                session.delete(db_movie)

    def __contains__(self, entry):
        return self._find_entry(entry) is not None

    @with_session
    def _find_entry(self, entry, session=None):
        """Finds `MovieListMovie` corresponding to this entry, if it exists."""
        # Match by supported IDs
        for id_name in MovieListBase().supported_ids:
            if entry.get(id_name):
                log.debug('trying to match movie based off id %s: %s', id_name, entry[id_name])
                res = (self._db_list(session).movies.join(MovieListMovie.ids).filter(
                    and_(
                        MovieListID.id_name == id_name,
                        MovieListID.id_value == entry[id_name]))
                       .first())
                if res:
                    log.debug('found movie %s', res)
                    return res
        # Fall back to title/year match
        if not entry.get('movie_name'):
            self._parse_title(entry)
        if entry.get('movie_name'):
            name = entry['movie_name']
            year = entry.get('movie_year') if entry.get('movie_year') else None
        else:
            log.warning('Could not get a movie name, skipping')
            return
        log.debug('trying to match movie based of name: %s and year: %s', name, year)
        res = (self._db_list(session).movies.filter(func.lower(MovieListMovie.title) == name.lower())
               .filter(MovieListMovie.year == year).first())
        if res:
            log.debug('found movie %s', res)
        return res

    @staticmethod
    def _parse_title(entry):
        parser = get_plugin_by_name('parsing').instance.parse_movie(data=entry['title'])
        if parser and parser.valid:
            parser.name = normalize_name(remove_dirt(parser.name))
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


class PluginMovieList(object):
    """Remove all accepted elements from your trakt.tv watchlist/library/seen or custom list."""
    schema = {'oneOf': [
        {'type': 'string'},
        {'type': 'object',
         'properties': {
             'list_name': {'type': 'string'},
             'strip_year': {'type': 'boolean'}
         },
         'required': ['list_name'],
         'additionalProperties': False
         }
    ]}

    @staticmethod
    def get_list(config):
        return MovieList(config)

    def on_task_input(self, task, config):
        return list(MovieList(config))


@event('plugin.register')
def register_plugin():
    plugin.register(PluginMovieList, 'movie_list', api_ver=2, groups=['list'])


@with_session
def get_movies_by_list_id(list_id, start=None, stop=None, order_by='added', descending=False,
                          session=None):
    query = session.query(MovieListMovie).filter(MovieListMovie.list_id == list_id)
    if descending:
        query = query.order_by(getattr(MovieListMovie, order_by).desc())
    else:
        query = query.order_by(getattr(MovieListMovie, order_by))
    return query.slice(start, stop).all()


@with_session
def get_movie_lists(name=None, session=None):
    log.debug('retrieving movie lists')
    query = session.query(MovieListList)
    if name:
        log.debug('filtering by name %s', name)
        query = query.filter(MovieListList.name.contains(name))
    return query.all()


@with_session
def get_list_by_exact_name(name, session=None):
    log.debug('returning list with name %s', name)
    return session.query(MovieListList).filter(func.lower(MovieListList.name) == name.lower()).one()


@with_session
def get_list_by_id(list_id, session=None):
    log.debug('fetching list with id %d', list_id)
    return session.query(MovieListList).filter(MovieListList.id == list_id).one()


@with_session
def get_movie_by_id(list_id, movie_id, session=None):
    log.debug('fetching movie with id %d from list id %d', movie_id, list_id)
    return session.query(MovieListMovie).filter(
        and_(MovieListMovie.id == movie_id, MovieListMovie.list_id == list_id)).one()


@with_session
def get_movie_by_title_and_year(list_id, title, year=None, session=None):
    movie_list = get_list_by_id(list_id=list_id, session=session)
    if movie_list:
        log.debug('searching for movie %s in list %d', title, list_id)
        return session.query(MovieListMovie).filter(
            and_(
                func.lower(MovieListMovie.title) == title.lower(),
                MovieListMovie.year == year,
                MovieListMovie.list_id == list_id)
        ).one_or_none()


@with_session
def get_movie_identifier(identifier_name, identifier_value, movie_id=None, session=None):
    db_movie_id = session.query(MovieListID).filter(
        and_(MovieListID.id_name == identifier_name,
             MovieListID.id_value == identifier_value,
             MovieListID.movie_id == movie_id)).first()
    if db_movie_id:
        log.debug('fetching movie identifier %s: %s', db_movie_id.id_name, db_movie_id.id_value)
        return db_movie_id


@with_session
def get_db_movie_identifiers(identifier_list, movie_id=None, session=None):
    db_movie_ids = []
    for identifier in identifier_list:
        for key, value in identifier.items():
            if key in MovieListBase().supported_ids:
                db_movie_id = get_movie_identifier(identifier_name=key, identifier_value=value, movie_id=movie_id,
                                                   session=session)
                if not db_movie_id:
                    log.debug('creating movie identifier %s: %s', key, value)
                    db_movie_id = MovieListID(id_name=key, id_value=value, movie_id=movie_id)
                session.merge(db_movie_id)
                db_movie_ids.append(db_movie_id)
    return db_movie_ids
