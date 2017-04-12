from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
from datetime import datetime, timedelta

from sqlalchemy import Table, Column, Integer, Float, String, Unicode, Boolean, DateTime
from sqlalchemy.schema import ForeignKey, Index
from sqlalchemy.orm import relation

from flexget import db_schema, plugin
from flexget.db_schema import UpgradeImpossible
from flexget.event import event
from flexget.entry import Entry
from flexget.utils.log import log_once
from flexget.utils.imdb import ImdbSearch, ImdbParser, extract_id, make_url
from flexget.utils.database import with_session

SCHEMA_VER = 8

Base = db_schema.versioned_base('imdb_lookup', SCHEMA_VER)

# association tables
genres_table = Table('imdb_movie_genres', Base.metadata,
                     Column('movie_id', Integer, ForeignKey('imdb_movies.id')),
                     Column('genre_id', Integer, ForeignKey('imdb_genres.id')),
                     Index('ix_imdb_movie_genres', 'movie_id', 'genre_id'))
Base.register_table(genres_table)

actors_table = Table('imdb_movie_actors', Base.metadata,
                     Column('movie_id', Integer, ForeignKey('imdb_movies.id')),
                     Column('actor_id', Integer, ForeignKey('imdb_actors.id')),
                     Index('ix_imdb_movie_actors', 'movie_id', 'actor_id'))
Base.register_table(actors_table)

directors_table = Table('imdb_movie_directors', Base.metadata,
                        Column('movie_id', Integer, ForeignKey('imdb_movies.id')),
                        Column('director_id', Integer, ForeignKey('imdb_directors.id')),
                        Index('ix_imdb_movie_directors', 'movie_id', 'director_id'))
Base.register_table(directors_table)

writers_table = Table('imdb_movie_writers', Base.metadata,
                      Column('movie_id', Integer, ForeignKey('imdb_movies.id')),
                      Column('writer_id', Integer, ForeignKey('imdb_writers.id')),
                      Index('ix_imdb_movie_writers', 'movie_id', 'writer_id'))
Base.register_table(writers_table)


class Movie(Base):
    __tablename__ = 'imdb_movies'

    id = Column(Integer, primary_key=True)
    title = Column(Unicode)
    original_title = Column(Unicode)
    url = Column(String, index=True)

    # many-to-many relations
    genres = relation('Genre', secondary=genres_table, backref='movies')
    actors = relation('Actor', secondary=actors_table, backref='movies')
    directors = relation('Director', secondary=directors_table, backref='movies')
    writers = relation('Writer', secondary=writers_table, backref='movies')
    languages = relation('MovieLanguage', order_by='MovieLanguage.prominence')

    score = Column(Float)
    votes = Column(Integer)
    year = Column(Integer)
    plot_outline = Column(Unicode)
    mpaa_rating = Column(String, default='')
    photo = Column(String)

    # updated time, so we can grab new rating counts after 48 hours
    # set a default, so existing data gets updated with a rating
    updated = Column(DateTime)

    @property
    def imdb_id(self):
        return extract_id(self.url)

    @property
    def expired(self):
        """
        :return: True if movie details are considered to be expired, ie. need of update
        """
        if self.updated is None:
            log.debug('updated is None: %s' % self)
            return True
        refresh_interval = 2
        if self.year:
            # Make sure age is not negative
            age = max((datetime.now().year - self.year), 0)
            refresh_interval += age * 5
            log.debug('movie `%s` age %i expires in %i days' % (self.title, age, refresh_interval))
        return self.updated < datetime.now() - timedelta(days=refresh_interval)

    def __repr__(self):
        return '<Movie(name=%s,votes=%s,year=%s)>' % (self.title, self.votes, self.year)


class MovieLanguage(Base):
    __tablename__ = 'imdb_movie_languages'

    movie_id = Column(Integer, ForeignKey('imdb_movies.id'), primary_key=True)
    language_id = Column(Integer, ForeignKey('imdb_languages.id'), primary_key=True)
    prominence = Column(Integer)

    language = relation('Language')

    def __init__(self, language, prominence=None):
        self.language = language
        self.prominence = prominence


class Language(Base):
    __tablename__ = 'imdb_languages'

    id = Column(Integer, primary_key=True)
    name = Column(Unicode)

    def __init__(self, name):
        self.name = name


class Genre(Base):
    __tablename__ = 'imdb_genres'

    id = Column(Integer, primary_key=True)
    name = Column(String)

    def __init__(self, name):
        self.name = name


class Actor(Base):
    __tablename__ = 'imdb_actors'

    id = Column(Integer, primary_key=True)
    imdb_id = Column(String)
    name = Column(Unicode)

    def __init__(self, imdb_id, name=None):
        self.imdb_id = imdb_id
        self.name = name


class Director(Base):
    __tablename__ = 'imdb_directors'

    id = Column(Integer, primary_key=True)
    imdb_id = Column(String)
    name = Column(Unicode)

    def __init__(self, imdb_id, name=None):
        self.imdb_id = imdb_id
        self.name = name


class Writer(Base):
    __tablename__ = 'imdb_writers'

    id = Column(Integer, primary_key=True)
    imdb_id = Column(String)
    name = Column(Unicode)

    def __init__(self, imdb_id, name=None):
        self.imdb_id = imdb_id
        self.name = name


class SearchResult(Base):
    __tablename__ = 'imdb_search'

    id = Column(Integer, primary_key=True)
    title = Column(Unicode, index=True)
    url = Column(String)
    fails = Column(Boolean, default=False)
    queried = Column(DateTime)

    @property
    def imdb_id(self):
        return extract_id(self.url)

    def __init__(self, title, url=None):
        self.title = title
        self.url = url
        self.queried = datetime.now()

    def __repr__(self):
        return '<SearchResult(title=%s,url=%s,fails=%s)>' % (self.title, self.url, self.fails)


log = logging.getLogger('imdb_lookup')


@db_schema.upgrade('imdb_lookup')
def upgrade(ver, session):
    # v5 We may have cached bad data due to imdb changes, just wipe everything. GitHub #697
    # v6 The association tables were not cleared on the last upgrade, clear again. GitHub #714
    # v7 Another layout change cached bad data. GitHub #729
    # v8 Added writers to the DB Schema
    if ver is None or ver <= 7:
        raise UpgradeImpossible('Resetting imdb_lookup caches because bad data may have been cached.')
    return ver


class ImdbLookup(object):
    """
        Retrieves imdb information for entries.

        Example:

        imdb_lookup: yes

        Also provides imdb lookup functionality to all other imdb related plugins.
    """

    field_map = {
        'imdb_url': 'url',
        'imdb_id': lambda movie: extract_id(movie.url),
        'imdb_name': 'title',
        'imdb_original_name': 'original_title',
        'imdb_photo': 'photo',
        'imdb_plot_outline': 'plot_outline',
        'imdb_score': 'score',
        'imdb_votes': 'votes',
        'imdb_year': 'year',
        'imdb_genres': lambda movie: [genre.name for genre in movie.genres],
        'imdb_languages': lambda movie: [lang.language.name for lang in movie.languages],
        'imdb_actors': lambda movie: dict((actor.imdb_id, actor.name) for actor in movie.actors),
        'imdb_directors': lambda movie: dict((director.imdb_id, director.name) for director in movie.directors),
        'imdb_writers': lambda movie: dict((writer.imdb_id, writer.name) for writer in movie.writers),
        'imdb_mpaa_rating': 'mpaa_rating',
        # Generic fields filled by all movie lookup plugins:
        'movie_name': 'title',
        'movie_year': 'year'}

    schema = {'type': 'boolean'}

    @plugin.priority(130)
    def on_task_metainfo(self, task, config):
        if not config:
            return
        for entry in task.entries:
            self.register_lazy_fields(entry)

    def register_lazy_fields(self, entry):
        entry.register_lazy_func(self.lazy_loader, self.field_map)

    def lazy_loader(self, entry):
        """Does the lookup for this entry and populates the entry fields."""
        try:
            self.lookup(entry)
        except plugin.PluginError as e:
            log_once(str(e.value).capitalize(), logger=log)

    @with_session
    def imdb_id_lookup(self, movie_title=None, movie_year=None, raw_title=None, session=None):
        """
        Perform faster lookup providing just imdb_id.
        Falls back to using basic lookup if data cannot be found from cache.

        .. note::

           API will be changed, it's dumb to return None on errors AND
           raise PluginError on some else

        :param movie_title: Name of the movie
        :param raw_title: Raw entry title
        :return: imdb id or None
        :raises PluginError: Failure reason
        """
        if movie_title:
            log.debug('imdb_id_lookup: trying with title: %s' % movie_title)
            query = session.query(Movie).filter(Movie.title == movie_title)
            if movie_year is not None:
                query = query.filter(Movie.year == movie_year)
            movie = query.first()
            if movie:
                log.debug('--> success! got %s returning %s' % (movie, movie.imdb_id))
                return movie.imdb_id
        if raw_title:
            log.debug('imdb_id_lookup: trying cache with: %s' % raw_title)
            result = session.query(SearchResult).filter(SearchResult.title == raw_title).first()
            if result:
                # this title is hopeless, give up ..
                if result.fails:
                    return None
                log.debug('--> success! got %s returning %s' % (result, result.imdb_id))
                return result.imdb_id
        if raw_title:
            # last hope with hacky lookup
            fake_entry = Entry(raw_title, '')
            self.lookup(fake_entry)
            return fake_entry['imdb_id']

    @plugin.internet(log)
    @with_session
    def lookup(self, entry, search_allowed=True, session=None):
        """
        Perform imdb lookup for entry.

        :param entry: Entry instance
        :param search_allowed: Allow fallback to search
        :raises PluginError: Failure reason
        """

        from flexget.manager import manager

        if entry.get('imdb_id', eval_lazy=False):
            log.debug('No title passed. Lookup for %s' % entry['imdb_id'])
        elif entry.get('imdb_url', eval_lazy=False):
            log.debug('No title passed. Lookup for %s' % entry['imdb_url'])
        elif entry.get('title', eval_lazy=False):
            log.debug('lookup for %s' % entry['title'])
        else:
            raise plugin.PluginError('looking up IMDB for entry failed, no title, imdb_url or imdb_id passed.')

        # if imdb_id is included, build the url.
        if entry.get('imdb_id', eval_lazy=False) and not entry.get('imdb_url', eval_lazy=False):
            entry['imdb_url'] = make_url(entry['imdb_id'])

        # make sure imdb url is valid
        if entry.get('imdb_url', eval_lazy=False):
            imdb_id = extract_id(entry['imdb_url'])
            if imdb_id:
                entry['imdb_url'] = make_url(imdb_id)
            else:
                log.debug('imdb url %s is invalid, removing it' % entry['imdb_url'])
                del (entry['imdb_url'])

        # no imdb_url, check if there is cached result for it or if the
        # search is known to fail
        if not entry.get('imdb_url', eval_lazy=False):
            result = session.query(SearchResult).filter(SearchResult.title == entry['title']).first()
            if result:
                # TODO: 1.2 this should really be checking task.options.retry
                if result.fails and not manager.options.execute.retry:
                    # this movie cannot be found, not worth trying again ...
                    log.debug('%s will fail lookup' % entry['title'])
                    raise plugin.PluginError('IMDB lookup failed for %s' % entry['title'])
                else:
                    if result.url:
                        log.trace('Setting imdb url for %s from db' % entry['title'])
                        entry['imdb_id'] = result.imdb_id
                        entry['imdb_url'] = result.url

        # no imdb url, but information required, try searching
        if not entry.get('imdb_url', eval_lazy=False) and search_allowed:
            log.verbose('Searching from imdb `%s`' % entry['title'])
            search = ImdbSearch()
            search_name = entry.get('movie_name', entry['title'], eval_lazy=False)
            search_result = search.smart_match(search_name)
            if search_result:
                entry['imdb_url'] = search_result['url']
                # store url for this movie, so we don't have to search on every run
                result = SearchResult(entry['title'], entry['imdb_url'])
                session.add(result)
                session.commit()
                log.verbose('Found %s' % (entry['imdb_url']))
            else:
                log_once('IMDB lookup failed for %s' % entry['title'], log, logging.WARN, session=session)
                # store FAIL for this title
                result = SearchResult(entry['title'])
                result.fails = True
                session.add(result)
                session.commit()
                raise plugin.PluginError('Title `%s` lookup failed' % entry['title'])

        # check if this imdb page has been parsed & cached
        movie = session.query(Movie).filter(Movie.url == entry['imdb_url']).first()

        # If we have a movie from cache, we are done
        if movie and not movie.expired:
            entry.update_using_map(self.field_map, movie)
            return

        # Movie was not found in cache, or was expired
        if movie is not None:
            if movie.expired:
                log.verbose('Movie `%s` details expired, refreshing ...' % movie.title)
            # Remove the old movie, we'll store another one later.
            session.query(MovieLanguage).filter(MovieLanguage.movie_id == movie.id).delete()
            session.query(Movie).filter(Movie.url == entry['imdb_url']).delete()
            session.commit()

        # search and store to cache
        if 'title' in entry:
            log.verbose('Parsing imdb for `%s`' % entry['title'])
        else:
            log.verbose('Parsing imdb for `%s`' % entry['imdb_id'])
        try:
            movie = self._parse_new_movie(entry['imdb_url'], session)
        except UnicodeDecodeError:
            log.error('Unable to determine encoding for %s. Installing chardet library may help.' %
                      entry['imdb_url'])
            # store cache so this will not be tried again
            movie = Movie()
            movie.url = entry['imdb_url']
            session.add(movie)
            session.commit()
            raise plugin.PluginError('UnicodeDecodeError')
        except ValueError as e:
            # TODO: might be a little too broad catch, what was this for anyway? ;P
            if manager.options.debug:
                log.exception(e)
            raise plugin.PluginError('Invalid parameter: %s' % entry['imdb_url'], log)

        for att in ['title', 'score', 'votes', 'year', 'genres', 'languages', 'actors', 'directors', 'writers',
                    'mpaa_rating']:
            log.trace('movie.%s: %s' % (att, getattr(movie, att)))

        # Update the entry fields
        entry.update_using_map(self.field_map, movie)

    def _parse_new_movie(self, imdb_url, session):
        """
        Get Movie object by parsing imdb page and save movie into the database.

        :param imdb_url: IMDB url
        :param session: Session to be used
        :return: Newly added Movie
        """
        parser = ImdbParser()
        parser.parse(imdb_url)
        # store to database
        movie = Movie()
        movie.photo = parser.photo
        movie.title = parser.name
        movie.original_title = parser.original_name
        movie.score = parser.score
        movie.votes = parser.votes
        movie.year = parser.year
        movie.mpaa_rating = parser.mpaa_rating
        movie.plot_outline = parser.plot_outline
        movie.url = imdb_url
        for name in parser.genres:
            genre = session.query(Genre).filter(Genre.name == name).first()
            if not genre:
                genre = Genre(name)
            movie.genres.append(genre)  # pylint:disable=E1101
        for index, name in enumerate(parser.languages):
            language = session.query(Language).filter(Language.name == name).first()
            if not language:
                language = Language(name)
            movie.languages.append(MovieLanguage(language, prominence=index))
        for imdb_id, name in parser.actors.items():
            actor = session.query(Actor).filter(Actor.imdb_id == imdb_id).first()
            if not actor:
                actor = Actor(imdb_id, name)
            movie.actors.append(actor)  # pylint:disable=E1101
        for imdb_id, name in parser.directors.items():
            director = session.query(Director).filter(Director.imdb_id == imdb_id).first()
            if not director:
                director = Director(imdb_id, name)
            movie.directors.append(director)  # pylint:disable=E1101
        for imdb_id, name in parser.writers.items():
            writer = session.query(Writer).filter(Writer.imdb_id == imdb_id).first()
            if not writer:
                writer = Writer(imdb_id, name)
            movie.writers.append(writer)  # pylint:disable=E1101
            # so that we can track how long since we've updated the info later
        movie.updated = datetime.now()
        session.add(movie)
        return movie

    @property
    def movie_identifier(self):
        """Returns the plugin main identifier type"""
        return 'imdb_id'


@event('plugin.register')
def register_plugin():
    plugin.register(ImdbLookup, 'imdb_lookup', api_ver=2, interfaces=['task', 'movie_metainfo'])
