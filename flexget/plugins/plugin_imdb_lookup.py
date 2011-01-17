import logging
from optparse import SUPPRESS_HELP
from flexget.plugin import register_plugin, register_parser_option, priority, internet, PluginError, PluginWarning
from flexget.manager import Base, Session
from flexget.utils.log import log_once
from flexget.utils.imdb import ImdbSearch, ImdbParser, extract_id
from sqlalchemy import Table, Column, Integer, Float, String, Unicode, Boolean, DateTime
from sqlalchemy.schema import ForeignKey
from sqlalchemy.orm import relation, joinedload_all
from datetime import datetime, timedelta

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
        return '<Movie(name=%s,votes=%s,year=%s)>' % (self.title, 
                                                      self.votes, 
                                                      self.year)


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


class ModuleImdbLookup(object):
    """
        Retrieves imdb information for entries.

        Example:

        imdb_lookup: yes

        Also provides imdb lookup functionality to all other imdb related plugins.
    """

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    @priority(100)
    def on_feed_filter(self, feed):
        from flexget.utils.log import log_once
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

        if 'title' in entry:
            log.debug('lookup for %s' % entry['title'])
        elif 'imdb_url' in entry:
            log.debug('No title passed. Lookup for %s' % entry['imdb_url'])
        elif 'imdb_id' in entry:
            log.debug('No title passed. Lookup for %s' % entry['imdb_id'])
        else:
            log.error('looking up IMDB for entry failed, no title, '
                      'imdb_url or imdb_id passed.')
            return

        take_a_break = False
        session = Session()

        try:
            # entry sanity checks
            for field in ['imdb_votes', 'imdb_score']:
                if field in entry:
                    value = entry[field]
                    if (not isinstance(value, int) and 
                        not isinstance(value, float)):
                        raise PluginError('Entry field %s should be a number!'\
                                          % field)

            # if imdb_id is included, build the url.
            if 'imdb_id' in entry and not 'imdb_url' in entry:
                entry['imdb_url'] = 'http://www.imdb.com/title/%s' %\
                     entry['imdb_id']
            
            # make sure imdb url is valid
            if 'imdb_url' in entry:
                imdb_id = extract_id(entry['imdb_url'])
                if imdb_id:
                    entry['imdb_url'] = 'http://www.imdb.com/title/%s' % imdb_id
                else:
                    log.debug('imdb url %s is invalid, removing it' %\
                              entry['imdb_url'])
                    del(entry['imdb_url'])

            # no imdb_url, check if there is cached result for it or if the 
            # search is known to fail
            if not 'imdb_url' in entry:
                result = session.query(SearchResult).filter(SearchResult.title 
                                                    == entry['title']).first()
                if result:
                    if result.fails and not feed.manager.options.retry_lookup:
                        # this movie cannot be found, not worth trying again ...
                        log.debug('%s will fail lookup' % entry['title'])
                        raise PluginError('Title lookup fails')
                    else:
                        if result.url:
                            log.log(5, 'Setting imdb url for %s from db' % 
                                    entry['title'])
                            entry['imdb_url'] = result.url

            # no imdb url, but information required, try searching
            if not 'imdb_url' in entry and search_allowed:
                feed.verbose_progress('Searching from imdb %s' % entry['title'])

                take_a_break = True
                search = ImdbSearch()
                search_result = search.smart_match(entry['title'])
                if search_result:
                    entry['imdb_url'] = search_result['url']
                    # store url for this movie, so we don't have to search on 
                    # every run
                    result = SearchResult(entry['title'], entry['imdb_url'])
                    session.add(result)
                    feed.verbose_progress('Found %s' % (entry['imdb_url']), log)
                else:
                    log_once('Imdb lookup failed for %s' % entry['title'], log)
                    # store FAIL for this title
                    result = SearchResult(entry['title'])
                    result.fails = True
                    session.add(result)
                    raise PluginError('Title lookup failed')

            imdb = ImdbParser()

            # check if this imdb page has been parsed & cached
            cached = session.query(Movie).\
                options(joinedload_all(Movie.genres, Movie.languages, 
                                       Movie.actors, Movie.directors)).\
                filter(Movie.url == entry['imdb_url']).first()
            if (not cached) or (cached.updated is None) or (cached.updated < 
                                            datetime.now() - timedelta(days=2)):
                # Remove the old movie, we'll store another one later.
                session.query(Movie).filter(Movie.url == entry['imdb_url'])\
                       .delete()
                # search and store to cache
                if 'title' in entry:
                    feed.verbose_progress('Parsing imdb for %s' % 
                                          entry['title'])
                else:
                    feed.verbose_progress('Parsing imdb for %s' % 
                                          entry['imdb_id'])
                try:
                    take_a_break = True
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
                        genre = session.query(Genre).filter(Genre.name == name)\
                              .first()
                        if not genre:
                            genre = Genre(name)
                        movie.genres.append(genre) # pylint:disable=E1101
                    for name in imdb.languages:
                        language = session.query(Language).filter(Language.name 
                                                            == name).first()
                        if not language:
                            language = Language(name)
                        movie.languages.append(language) # pylint:disable=E1101
                    for imdb_id, name in imdb.actors.iteritems():
                        actor = session.query(Actor).filter(Actor.imdb_id 
                                                            == imdb_id).first()
                        if not actor:
                            actor = Actor(imdb_id, name)
                        movie.actors.append(actor) # pylint:disable=E1101
                    for imdb_id, name in imdb.directors.iteritems():
                        director = session.query(Director)\
                                 .filter(Director.imdb_id == imdb_id).first()
                        if not director:
                            director = Director(imdb_id, name)
                        movie.directors.append(director) # pylint:disable=E1101
                    # so that we can track how long since we've updated the info later
                    movie.updated = datetime.now()
                    output = session.add(movie)

                except UnicodeDecodeError:
                    log.error('Unable to determine encoding for %s. Installing chardet library may help.' % entry['imdb_url'])
                    # store cache so this will not be tried again
                    movie = Movie()
                    movie.url = entry['imdb_url']
                    session.add(movie)
                    raise PluginWarning('UnicodeDecodeError')
                except ValueError, e:
                    # TODO: might be a little too broad catch, what was this for anyway? ;P
                    if feed.manager.options.debug:
                        log.exception(e)
                    raise PluginError('Invalid parameter: %s' % 
                                      entry['imdb_url'], log)
            else:
                # Set values from cache
                # TODO: I don't like this shoveling ...
                imdb.url = cached.url
                imdb.photo = cached.photo
                imdb.name = cached.title
                imdb.year = cached.year
                imdb.votes = cached.votes
                imdb.score = cached.score
                imdb.mpaa_rating = cached.mpaa_rating
                imdb.plot_outline = cached.plot_outline
                imdb.genres = [genre.name for genre in cached.genres]
                imdb.languages = [lang.name for lang in cached.languages]
                for actor in cached.actors:
                    imdb.actors[actor.imdb_id] = actor.name
                for director in cached.directors:
                    imdb.directors[director.imdb_id] = director.name

            if imdb.mpaa_rating is None:
                imdb.mpaa_rating = ''
            
            log.log(5, 'imdb.name: %s' % imdb.name)
            log.log(5, 'imdb.score: %s' % imdb.score)
            log.log(5, 'imdb.votes: %s' % imdb.votes)
            log.log(5, 'imdb.year: %s' % imdb.year)
            log.log(5, 'imdb.genres: %s' % imdb.genres)
            log.log(5, 'imdb.languages: %s' % imdb.languages)
            log.log(5, 'imdb.actors: %s' % ', '.join(imdb.actors))
            log.log(5, 'imdb.directors: %s' % ', '.join(imdb.directors))
            log.log(5, 'imdb.mpaa_rating: %s' % ', '.join(imdb.mpaa_rating))

            # store to entry
            # TODO: I really don't like this shoveling!
            entry['imdb_url'] = imdb.url
            entry['imdb_id'] = imdb.imdb_id
            entry['imdb_name'] = imdb.name
            entry['imdb_photo'] = imdb.photo
            entry['imdb_plot_outline'] = imdb.plot_outline
            entry['imdb_score'] = imdb.score
            entry['imdb_votes'] = imdb.votes
            entry['imdb_year'] = imdb.year
            entry['imdb_genres'] = imdb.genres
            entry['imdb_languages'] = imdb.languages
            entry['imdb_actors'] = imdb.actors
            entry['imdb_directors'] = imdb.directors
            entry['imdb_mpaa_rating'] = imdb.mpaa_rating
            if not 'title' in entry:
                entry['title'] = imdb.name

            # give imdb a little break between requests (see: http://flexget.com/ticket/129#comment:1)
            if (take_a_break and 
                not feed.manager.options.debug and 
                not feed.manager.unit_test):
                import time
                time.sleep(3)
        finally:
            log.log(5, 'committing session')
            session.commit()

register_plugin(ModuleImdbLookup, 'imdb_lookup')
register_parser_option('--retry-lookup', action='store_true', 
                       dest='retry_lookup', default=0, help=SUPPRESS_HELP)
