import logging
from datetime import datetime, timedelta
from flexget.utils.sqlalchemy_utils import table_columns
from sqlalchemy import Table, Column, Integer, Float, String, Unicode, Boolean, DateTime
from sqlalchemy.schema import ForeignKey
from sqlalchemy.orm import relation, joinedload_all
from flexget import schema
from flexget.plugin import register_plugin, priority, internet, PluginError, PluginWarning
from flexget.manager import Session
from flexget.utils.log import log_once
from flexget.utils.imdb import ImdbSearch, ImdbParser, extract_id, make_url
from flexget.utils.sqlalchemy_utils import table_add_column

Base = schema.versioned_base('imdb_lookup', 0)

# association tables
genres_table = Table('imdb_movie_genres', Base.metadata,
    Column('movie_id', Integer, ForeignKey('imdb_movies.id')),
    Column('genre_id', Integer, ForeignKey('imdb_genres.id')))

languages_table = Table('imdb_movie_languages', Base.metadata,
    Column('movie_id', Integer, ForeignKey('imdb_movies.id')),
    Column('language_id', Integer, ForeignKey('imdb_languages.id')))

actors_table = Table('imdb_movie_actors', Base.metadata,
    Column('movie_id', Integer, ForeignKey('imdb_movies.id')),
    Column('actor_id', Integer, ForeignKey('imdb_actors.id')))

directors_table = Table('imdb_movie_directors', Base.metadata,
    Column('movie_id', Integer, ForeignKey('imdb_movies.id')),
    Column('director_id', Integer, ForeignKey('imdb_directors.id')))


class Movie(Base):

    __tablename__ = 'imdb_movies'

    id = Column(Integer, primary_key=True)
    title = Column(Unicode)
    url = Column(String, index=True)

    # many-to-many relations
    genres = relation('Genre', secondary=genres_table, backref='movies')
    languages = relation('Language', secondary=languages_table, backref='movies')
    actors = relation('Actor', secondary=actors_table, backref='movies')
    directors = relation('Director', secondary=directors_table, backref='movies')

    score = Column(Float)
    votes = Column(Integer)
    year = Column(Integer)
    plot_outline = Column(Unicode)
    mpaa_rating = Column(String, default='')
    photo = Column(String)

    # updated time, so we can grab new rating counts after 48 hours
    # set a default, so existing data gets updated with a rating
    updated = Column(DateTime)

    def __repr__(self):
        return '<Movie(name=%s,votes=%s,year=%s)>' % (self.title, self.votes, self.year)


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


class SearchResult(Base):

    __tablename__ = 'imdb_search'

    id = Column(Integer, primary_key=True)
    title = Column(Unicode, index=True)
    url = Column(String)
    fails = Column(Boolean, default=False)

    def __init__(self, title, url=None):
        self.title = title
        self.url = url

log = logging.getLogger('imdb_lookup')


@schema.upgrade('imdb_lookup')
def upgrade(ver, session):
    if ver is None:
        columns = table_columns('imdb_movies', session)
        if not 'photo' in columns:
            log.info('Adding photo column to imdb_movies table.')
            table_add_column('imdb_movies', 'photo', String, session)
        if not 'updated' in columns:
            log.info('Adding updated column to imdb_movies table.')
            table_add_column('imdb_movies', 'updated', DateTime, session)
        if not 'mpaa_rating' in columns:
            log.info('Adding mpaa_rating column to imdb_movies table.')
            table_add_column('imdb_movies', 'mpaa_rating', String, session)
        ver = 0
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
        'imdb_photo': 'photo',
        'imdb_plot_outline': 'plot_outline',
        'imdb_score': 'score',
        'imdb_votes': 'votes',
        'imdb_year': 'year',
        'imdb_genres': lambda movie: [genre.name for genre in movie.genres],
        'imdb_languages': lambda movie: [lang.name for lang in movie.languages],
        'imdb_actors': lambda movie: dict((actor.imdb_id, actor.name) for actor in movie.actors),
        'imdb_directors': lambda movie: dict((director.imdb_id, director.name) for director in movie.directors),
        'imdb_mpaa_rating': 'mpaa_rating'}

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    @priority(100)
    def on_feed_filter(self, feed, config):
        if not config:
            return
        for entry in feed.entries:
            try:
                self.lookup(feed, entry)
            except PluginError, e:
                log_once(e.value.capitalize(), logger=log)
            except PluginWarning, e:
                log_once(e.value.capitalize(), logger=log)

    @internet(log)
    def lookup(self, feed, entry, search_allowed=True):
        """Perform imdb lookup for entry.
        Raises PluginError with failure reason."""

        if 'imdb_url' in entry:
            log.debug('No title passed. Lookup for %s' % entry['imdb_url'])
        elif 'imdb_id' in entry:
            log.debug('No title passed. Lookup for %s' % entry['imdb_id'])
        elif 'title' in entry:
            log.debug('lookup for %s' % entry['title'])
        else:
            raise PluginError('looking up IMDB for entry failed, no title, imdb_url or imdb_id passed.')

        take_a_break = False
        session = Session()

        try:
            # entry sanity checks
            for field in ['imdb_votes', 'imdb_score']:
                if field in entry:
                    value = entry[field]
                    if not isinstance(value, (int, float)):
                        raise PluginError('Entry field %s should be a number!' % field)

            # if imdb_id is included, build the url.
            if 'imdb_id' in entry and not 'imdb_url' in entry:
                entry['imdb_url'] = make_url(entry['imdb_id'])

            # make sure imdb url is valid
            if 'imdb_url' in entry:
                imdb_id = extract_id(entry['imdb_url'])
                if imdb_id:
                    entry['imdb_url'] = make_url(imdb_id)
                else:
                    log.debug('imdb url %s is invalid, removing it' % entry['imdb_url'])
                    del(entry['imdb_url'])

            # no imdb_url, check if there is cached result for it or if the
            # search is known to fail
            if not 'imdb_url' in entry:
                result = session.query(SearchResult).\
                         filter(SearchResult.title == entry['title']).first()
                if result:
                    if result.fails and not feed.manager.options.retry:
                        # this movie cannot be found, not worth trying again ...
                        log.debug('%s will fail lookup' % entry['title'])
                        raise PluginError('Title `%s` lookup fails' % entry['title'])
                    else:
                        if result.url:
                            log.debugall('Setting imdb url for %s from db' % entry['title'])
                            entry['imdb_url'] = result.url

            # no imdb url, but information required, try searching
            if not 'imdb_url' in entry and search_allowed:
                log.verbose('Searching from imdb %s' % entry['title'])

                take_a_break = True
                search = ImdbSearch()
                search_result = search.smart_match(entry['title'])
                if search_result:
                    entry['imdb_url'] = search_result['url']
                    # store url for this movie, so we don't have to search on
                    # every run
                    result = SearchResult(entry['title'], entry['imdb_url'])
                    session.add(result)
                    log.verbose('Found %s' % (entry['imdb_url']))
                else:
                    log_once('Imdb lookup failed for %s' % entry['title'], log)
                    # store FAIL for this title
                    result = SearchResult(entry['title'])
                    result.fails = True
                    session.add(result)
                    raise PluginError('Title `%s` lookup failed' % entry['title'])


            # check if this imdb page has been parsed & cached
            movie = session.query(Movie).\
                options(joinedload_all(Movie.genres, Movie.languages,
                Movie.actors, Movie.directors)).\
                filter(Movie.url == entry['imdb_url']).first()

            refresh_interval = 2
            if movie:
                if movie.year:
                    age = (datetime.now().year - movie.year)
                    refresh_interval += age * 5
                    log.debug('cached movie `%s` age %i refresh interval %i days' % (movie.title, age, refresh_interval))

            if not movie or movie.updated is None or \
               movie.updated < datetime.now() - timedelta(days=refresh_interval):
                # Remove the old movie, we'll store another one later.
                session.query(Movie).filter(Movie.url == entry['imdb_url']).delete()
                # search and store to cache
                if 'title' in entry:
                    log.verbose('Parsing imdb for `%s`' % entry['title'])
                else:
                    log.verbose('Parsing imdb for `%s`' % entry['imdb_id'])
                try:
                    take_a_break = True
                    imdb = ImdbParser()
                    imdb.parse(entry['imdb_url'])
                    # store to database
                    movie = Movie()
                    movie.photo = imdb.photo
                    movie.title = imdb.name
                    movie.score = imdb.score
                    movie.votes = imdb.votes
                    movie.year = imdb.year
                    movie.mpaa_rating = imdb.mpaa_rating
                    movie.plot_outline = imdb.plot_outline
                    movie.url = entry['imdb_url']
                    for name in imdb.genres:
                        genre = session.query(Genre).\
                            filter(Genre.name == name).first()
                        if not genre:
                            genre = Genre(name)
                        movie.genres.append(genre) # pylint:disable=E1101
                    for name in imdb.languages:
                        language = session.query(Language).\
                            filter(Language.name == name).first()
                        if not language:
                            language = Language(name)
                        movie.languages.append(language) # pylint:disable=E1101
                    for imdb_id, name in imdb.actors.iteritems():
                        actor = session.query(Actor).\
                            filter(Actor.imdb_id == imdb_id).first()
                        if not actor:
                            actor = Actor(imdb_id, name)
                        movie.actors.append(actor) # pylint:disable=E1101
                    for imdb_id, name in imdb.directors.iteritems():
                        director = session.query(Director).\
                            filter(Director.imdb_id == imdb_id).first()
                        if not director:
                            director = Director(imdb_id, name)
                        movie.directors.append(director) # pylint:disable=E1101
                    # so that we can track how long since we've updated the info later
                    movie.updated = datetime.now()
                    session.add(movie)

                except UnicodeDecodeError:
                    log.error('Unable to determine encoding for %s. Installing chardet library may help.' % entry['imdb_url'])
                    # store cache so this will not be tried again
                    movie = Movie()
                    movie.url = entry['imdb_url']
                    session.add(movie)
                    raise PluginError('UnicodeDecodeError')
                except ValueError, e:
                    # TODO: might be a little too broad catch, what was this for anyway? ;P
                    if feed.manager.options.debug:
                        log.exception(e)
                    raise PluginError('Invalid parameter: %s' % entry['imdb_url'], log)

            for att in ['title', 'score', 'votes', 'year', 'genres', 'languages', 'actors', 'directors', 'mpaa_rating']:
                log.debugall('movie.%s: %s' % (att, getattr(movie, att)))

            # store to entry
            entry.update_using_map(self.field_map, movie)

            # give imdb a little break between requests (see: http://flexget.com/ticket/129#comment:1)
            if (take_a_break and
                not feed.manager.options.debug and
                not feed.manager.unit_test):
                import time
                time.sleep(3)
        finally:
            log.debugall('committing session')
            session.commit()

register_plugin(ImdbLookup, 'imdb_lookup', api_ver=2)
