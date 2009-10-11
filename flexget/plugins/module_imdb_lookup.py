import logging
from optparse import SUPPRESS_HELP
from flexget.plugin import *
from flexget.manager import Base
from flexget.utils.log import log_once
from flexget.utils.imdb import ImdbSearch, ImdbParser

from sqlalchemy import Table, Column, Integer, Float, String, Unicode, DateTime, Boolean, PickleType
from sqlalchemy.schema import ForeignKey
from sqlalchemy.orm import relation

log = logging.getLogger('imdb')

# association tables
genres_table = Table('imdb_movie_genres', Base.metadata,
    Column('movie_id', Integer, ForeignKey('imdb_movies.id')),
    Column('genre_id', Integer, ForeignKey('imdb_genres.id'))
)

languages_table = Table('imdb_movie_languages', Base.metadata,
    Column('movie_id', Integer, ForeignKey('imdb_movies.id')),
    Column('language_id', Integer, ForeignKey('imdb_languages.id'))
)

actors_table = Table('imdb_movie_actors', Base.metadata,
    Column('movie_id', Integer, ForeignKey('imdb_movies.id')),
    Column('actor_id', Integer, ForeignKey('imdb_actors.id'))
)

directors_table = Table('imdb_movie_directors', Base.metadata,
    Column('movie_id', Integer, ForeignKey('imdb_movies.id')),
    Column('director_id', Integer, ForeignKey('imdb_directors.id'))
)

class Movie(Base):
    
    __tablename__ = 'imdb_movies'
    
    id = Column(Integer, primary_key=True)
    title = Column(String)
    url = Column(String)

    # many-to-many relations
    genres = relation('Genre', secondary=genres_table, backref='movies')
    languages = relation('Language', secondary=languages_table, backref='movies')
    actors = relation('Actor', secondary=actors_table, backref='movies')
    directors = relation('Director', secondary=directors_table, backref='movies')
    
    score = Column(Float)
    votes = Column(Integer)
    year = Column(Integer)
    plot_outline = Column(String)

    def __repr__(self):
        return '<Movie(name=%s,votes=%s,year=%s)>' % (self.title, self.votes, self.year)

class Language(Base):
    
    __tablename__ = 'imdb_languages'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    
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
    name = Column(String)

    def __init__(self, imdb_id, name="N/A"):
        self.imdb_id = imdb_id
        self.name = name

class Director(Base):
    __tablename__ = 'imdb_directors'

    id = Column(Integer, primary_key=True)
    imdb_id = Column(String)
    name = Column(String)

    def __init__(self, imdb_id, name="N/A"):
        self.imdb_id = imdb_id
        self.name = name

class SearchResult(Base):

    __tablename__ = 'imdb_search'

    id = Column(Integer, primary_key=True)
    title = Column(String)
    url = Column(String)
    fails = Column(Boolean, default=False) 
    
    def __init__(self, title, url=None):
        self.title = title
        self.url = url

log = logging.getLogger('imdb_lookup')

class ModuleImdbLookup:
    """
        Retrieves imdb information for entries.

        Example:

        imdb_lookup: yes
        
        Also provides imdb lookup functionality to all other imdb related plugins.
    """
    def validator(self):
        from flexget import validator
        return validator.factory('boolean')


    def clean_url(self, url):
        """Cleans imdb url, returns valid clean url or False"""
        import re
        match = re.search('(?:http://)?(?:www\.)?imdb.com/title/tt\d+', url)
        if match:
            return match.group()
        return False

    def on_feed_filter(self, feed):
        for entry in feed.entries:
            try:
                self.lookup(feed, entry)
            except PluginError, e:
                from flexget.utils.log import log_once
                log_once(e.value.capitalize(), logger=log)

    def lookup(self, feed, entry, search_allowed=True):
        """Perform imdb lookup for entry. Raises PluginError with failure reason."""
            
        take_a_break = False
        
        # entry sanity checks
        for field in ['imdb_votes', 'imdb_score']:
            if field in entry:
                value = entry[field]
                if not isinstance(value, int) and not isinstance(value, float):
                    raise PluginError('Entry field %s should be a number!' % field)
    
        # make sure imdb url is valid
        if 'imdb_url' in entry:
            clean = self.clean_url(entry['imdb_url'])
            if not clean:
                log.debug('imdb url %s is unclean, removing it' % entry['imdb_url'])
                del(entry['imdb_url'])
            else:
                entry['imdb_url'] = clean

        # no imdb_url, check if there is cached result for it or if the search is known to fail
        if not 'imdb_url' in entry:
            result = feed.session.query(SearchResult).filter(SearchResult.title==entry['title']).first()
            if result:
                if result.fails and not feed.manager.options.retry_lookup:
                    # this movie cannot be found, not worth trying again ...
                    log.debug('%s will fail lookup' % entry['title'])
                    raise PluginError('Lookup fails')
                else:
                    log.debug('Setting imdb url for %s from db' % entry['title'])
                    if result.url:
                        entry['imdb_url'] = result.url

        # no imdb url, but information required, try searching
        if not 'imdb_url' in entry and search_allowed:
            feed.verbose_progress('Searching from imdb %s' % entry['title'])
            try:
                take_a_break = True
                search = ImdbSearch()
                search_result = search.smart_match(entry['title'])
                if search_result:
                    entry['imdb_url'] = search_result['url']
                    # store url for this movie, so we don't have to search on every run
                    result = SearchResult(entry['title'], entry['imdb_url'])
                    feed.session.add(result)
                    log.info('Found %s' % (entry['imdb_url']))
                else:
                    log_once('Imdb lookup failed for %s' % entry['title'], log)
                    # store FAIL for this title
                    result = SearchResult(entry['title'])
                    result.fails = True
                    feed.session.add(result)
                    raise PluginError('Lookup failed')
            except IOError, e:
                if hasattr(e, 'reason'):
                    log.error('Failed to reach server. Reason: %s' % e.reason)
                elif hasattr(e, 'code'):
                    log.error('The server couldn\'t fulfill the request. Error code: %s' % e.code)
                raise PluginError('error occured')

        imdb = ImdbParser()
        
        # check if this imdb page has been parsed & cached
        cached = feed.session.query(Movie).filter(Movie.url==entry['imdb_url']).first()
        if not cached:
            # search and store to cache
            feed.verbose_progress('Parsing imdb for %s' % entry['title'])
            try:
                take_a_break = True
                imdb.parse(entry['imdb_url'])
                
                # store to database
                movie = Movie()
                movie.title = imdb.name
                movie.score = imdb.score
                movie.votes = imdb.votes
                movie.year = imdb.year                
                movie.plot_outline = imdb.plot_outline
                movie.url = entry['imdb_url']
                for name in imdb.genres:
                    genre = feed.session.query(Genre).filter(Genre.name==name).first()
                    if not genre:
                        genre = Genre(name)
                    movie.genres.append(genre) # pylint: disable-msg=E1101
                for name in imdb.languages:
                    language = feed.session.query(Language).filter(Language.name==name).first()
                    if not language:
                        language = Language(name)
                    movie.languages.append(language) # pylint: disable-msg=E1101
                for imdb_id in imdb.actors:
                    actor = feed.session.query(Actor).filter(Actor.imdb_id==imdb_id).first()
                    if not actor:
                        # TODO: Handle actor name
                        actor = Actor(imdb_id)
                    movie.actors.append(actor) # pylint: disable-msg=E1101
                for imdb_id in imdb.directors:
                    director = feed.session.query(Director).filter(Director.imdb_id==imdb_id).first()
                    if not director:
                        # TODO: Handle director name
                        director = Director(imdb_id)
                    movie.directors.append(director) # pylint: disable-msg=E1101
                feed.session.add(movie)                        
                
            except UnicodeDecodeError:
                log.error('Unable to determine encoding for %s. Installing chardet library may help.' % entry['imdb_url'])
                # store cache so this will not be tried again
                movie = Movie()
                movie.url = entry['imdb_url']
                feed.session.add(movie)
                raise PluginError('UnicodeDecodeError')
            except ValueError, e:
                if feed.manager.options.debug:
                    log.exception(e)
                log.error('Invalid parameter: %s' % entry['imdb_url'])
                raise PluginError('Parameters')
            except IOError, e:
                if hasattr(e, 'reason'):
                    log.error('Failed to reach server. Reason: %s' % e.reason)
                elif hasattr(e, 'code'):
                    log.error('The server couldn\'t fulfill the request. Error code: %s' % e.code)
                raise PluginError('Error occured')
            except Exception, e:
                log.error('Unable to process url %s' % entry['imdb_url'])
                log.exception(e)
                raise PluginError('Error occured')
        else:
            # Set values from cache
            # TODO: I don't like this shoveling ...
            imdb.url = cached.url
            imdb.name = cached.title
            imdb.year = cached.year
            imdb.votes = cached.votes
            imdb.score = cached.score
            imdb.plot_outline = cached.plot_outline
            imdb.genres = [genre.name for genre in cached.genres]
            imdb.languages = [lang.name for lang in cached.languages]
            imdb.actors = [actor.name for actor in cached.actors]
            imdb.directors = [director.name for director in cached.directors]

        log.log(5, 'imdb.score: %s' % imdb.score)
        log.log(5, 'imdb.votes: %s' % imdb.votes)
        log.log(5, 'imdb.year: %s' % imdb.year)
        log.log(5, 'imdb.genres: %s' % imdb.genres)
        log.log(5, 'imdb.languages: %s' % imdb.languages)
        log.log(5, 'imdb.actors: %s' % imdb.actors)
        log.log(5, 'imdb.directors: %s' % imdb.directors)
        
        # store to entries
        # TODO: I really don't like this shoveling!
        entry['imdb_url'] = imdb.url
        entry['imdb_name'] = imdb.name
        entry['imdb_plot_outline'] = imdb.plot_outline
        entry['imdb_score'] = imdb.score
        entry['imdb_votes'] = imdb.votes
        entry['imdb_year'] = imdb.year
        entry['imdb_genres'] = imdb.genres
        entry['imdb_languages'] = imdb.languages
        entry['imdb_actors'] = imdb.actors
        entry['imdb_directors'] = imdb.directors
        
        # give imdb a little break between requests (see: http://flexget.com/ticket/129#comment:1)
        if take_a_break and not feed.manager.options.debug and not feed.manager.unit_test:
            import time
            time.sleep(3)
        
register_plugin(ModuleImdbLookup, 'imdb_lookup', priorities={'filter': 128})
register_parser_option('--retry-lookup', action='store_true', dest='retry_lookup', default=0, help=SUPPRESS_HELP)
