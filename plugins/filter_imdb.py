import logging
from manager import PluginWarning, Base
from utils.log import log_once
from utils.imdb import ImdbSearch, ImdbParser

from sqlalchemy import Table, Column, Integer, Float, String, Unicode, DateTime, Boolean, PickleType
from sqlalchemy.schema import ForeignKey
from sqlalchemy.orm import relation

log = logging.getLogger('imdb')

# association tables
genres = Table('imdb_movie_genres', Base.metadata,
    Column('movie_id', Integer, ForeignKey('imdb_movies.id')),
    Column('genre_id', Integer, ForeignKey('imdb_genres.id'))
)

languages = Table('imdb_movie_languages', Base.metadata,
    Column('movie_id', Integer, ForeignKey('imdb_movies.id')),
    Column('language_id', Integer, ForeignKey('imdb_languages.id'))
)

class Movie(Base):
    
    __tablename__ = 'imdb_movies'
    
    id = Column(Integer, primary_key=True)
    title = Column(String)
    url = Column(String)

    # many-to-many relations
    genres = relation('Genre', secondary=genres, backref='movies')
    languages = relation('Language', secondary=languages, backref='movies')
    
    score = Column(Float)
    votes = Column(Integer)
    year = Column(Integer)
    year = Column(Integer)
    plot_outline = Column(String)

    def __repr__(self):
        return '<Movie(name=%s)>' % (self.title)

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

class SearchResult(Base):

    __tablename__ = 'imdb_search'

    id = Column(Integer, primary_key=True)
    title = Column(String)
    url = Column(String)
    fails = Column(Boolean, default=False) 
    
    def __init__(self, title, url=None):
        self.title = title
        self.url = url

log = logging.getLogger('imdb')

class FilterImdb:

    """
        This plugin allows filtering based on IMDB score, votes and genres etc.

        Configuration:
        
            Note: All parameters are optional. Some are mutually exclusive.
        
            min_score: <num>
            min_votes: <num>
            min_year: <num>

            # reject if genre contains any of these
            reject_genres:
                - genre1
                - genre2

            # reject if language contain any of these
            reject_languages:
                - language1

            # accept only this language
            accept_languages:
                - language1

            # filter all entries which are not imdb-compatible
            # this has default value (True) even when key not present
            filter_invalid: True / False
    """

    def register(self, manager, parser):
        manager.register('imdb')

    def validator(self):
        """Validate given configuration"""
        import validator
        imdb = validator.factory('dict')
        imdb.accept('number', key='min_year')
        imdb.accept('number', key='min_votes')
        imdb.accept('decimal', key='min_score')
        imdb.accept('list', key='reject_genres').accept('text')
        imdb.accept('list', key='reject_languages').accept('text')
        imdb.accept('list', key='accept_languages').accept('text')
        imdb.accept('boolean', key='filter_invalid')
        return imdb

    def imdb_required(self, entry, config):
        """Return True if config contains conditions that are NOT available in preparsed fields"""
        check = {'min_votes':'imdb_votes', 'min_score': 'imdb_score', 'reject_genres': 'imdb_genres',
                 'reject_languages': 'imdb_languages', 'accept_languages': 'imdb_languages'}
        for key, value in check.iteritems():
            if key in config and not value in entry: 
                return True
        return False
        
    def clean_url(self, url):
        """Cleans imdb url, returns valid clean url or False"""
        import re
        match = re.search('(http://.*imdb\.com\/title\/tt\d*\/)', url)
        if match:
            return match.group()
        return False

    def feed_filter(self, feed):
        config = feed.config['imdb']
        for entry in feed.entries:
        
            # sanity checks
            for field in ['imdb_votes', 'imdb_score']:
                if field in entry:
                    if not isinstance(entry[field], int):
                        raise PluginWarning('%s should be int!' % field)
        
            # make sure imdb url is valid
            if 'imdb_url' in entry:
                clean = self.clean_url(entry['imdb_url'])
                if not clean:
                    del(entry['imdb_url'])
                else:
                    entry['imdb_url'] = clean

            # no imdb_url, check if there is cached result for it or if the search is known to fail
            if not 'imdb_url' in entry:
                result = feed.session.query(SearchResult).filter(SearchResult.title==entry['title']).first()
                if result:
                    if result.fails:
                        # this movie cannot be found, not worth trying again ...
                        log.debug('%s will fail search, rejecting' % entry['title'])
                        feed.reject(entry, 'search failed')
                        continue
                    else:
                        log.debug('Setting imdb url for %s from db' % entry['title'])
                        entry['imdb_url'] = result.url

            # no imdb url, but information required, try searching
            if not 'imdb_url' in entry and self.imdb_required(entry, config):
                feed.verbose_progress('Searching from imdb %s' % entry['title'])
                try:
                    search = ImdbSearch()
                    search_result = search.smart_match(entry['title'])
                    if search_result:
                        entry['imdb_url'] = search_result['url']
                        # store url for this movie, so we don't have to search on every run
                        result = SearchResult(entry['title'], entry['imdb_url'])
                        feed.session.add(result)
                        log.info('Found %s' % (entry['imdb_url']))
                    else:
                        log_once('Imdb search failed for %s' % entry['title'], log)
                        # store FAIL for this title
                        result = SearchResult(entry['title'])
                        result.fails = True
                        feed.session.add(result)
                        # act depending configuration
                        if config.get('reject_invalid', True):
                            log_once('Rejecting %s because of undeterminable imdb url' % entry['title'], log)
                            feed.reject(entry, 'undeterminable url')
                        else:
                            log.debug('Unable to check %s due missing imdb url, configured to pass (filter_invalid is False)' % entry['title'])
                        continue
                except IOError, e:
                    if hasattr(e, 'reason'):
                        log.error('Failed to reach server. Reason: %s' % e.reason)
                    elif hasattr(e, 'code'):
                        log.error('The server couldn\'t fulfill the request. Error code: %s' % e.code)
                    feed.reject(entry, 'error occured')
                    continue

            imdb = ImdbParser()
            if self.imdb_required(entry, config):
                # check if this imdb page has been parsed & cached
                cached = feed.session.query(Movie).filter(Movie.url==entry['imdb_url']).first()
                if not cached:
                    feed.verbose_progress('Parsing from imdb %s' % entry['title'])
                    try:
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
                            movie.genres.append(genre)
                        for name in imdb.languages:
                            language = feed.session.query(Language).filter(Language.name==name).first()
                            if not language:
                                language = Language(name)
                            movie.languages.append(language)
                        feed.session.add(movie)                        
                        
                    except UnicodeDecodeError:
                        log.error('Unable to determine encoding for %s. Installing chardet library may help.' % entry['imdb_url'])
                        feed.reject(entry, 'UnicodeDecodeError')
                        # store cache so this will be skipped
                        movie = Movie()
                        movie.url = entry['imdb_url']
                        feed.session.add(movie)
                        continue
                    except ValueError:
                        log.error('Invalid parameter: %s' % entry['imdb_url'])
                        feed.reject(entry, 'parameters')
                        continue
                    except IOError, e:
                        if hasattr(e, 'reason'):
                            log.error('Failed to reach server. Reason: %s' % e.reason)
                        elif hasattr(e, 'code'):
                            log.error('The server couldn\'t fulfill the request. Error code: %s' % e.code)
                        feed.reject(entry, 'error occured')
                        continue
                    except Exception, e:
                        feed.reject(entry, 'error occured')
                        log.error('Unable to process url %s' % entry['imdb_url'])
                        log.exception(e)
                        continue
                else:
                    imdb.name = cached.title
                    imdb.year = cached.year
                    imdb.votes = cached.votes
                    imdb.score = cached.score
                    imdb.plot_outline = cached.plot_outline
                    imdb.genres = cached.genres
                    imdb.languages = cached.languages
            else:
                # Set few required fields manually from entry, and thus avoiding request & parse
                # Note: It doesn't matter even if some fields are missing, previous imdb_required
                # checks that those aren't required in condition check. So just set them all! :)
                imdb.votes = entry.get('imdb_votes', 0)
                imdb.score = entry.get('imdb_score', 0.0)
                imdb.year = entry.get('imdb_year', 0)
                imdb.languages = entry.get('imdb_languages', [])
                imdb.genres = entry.get('imdb_genres', [])

            # Check defined conditions, TODO: rewrite into functions?
            
            reasons = []
            if 'min_score' in config:
                if imdb.score < config['min_score']:
                    reasons.append('min_score (%s < %s)' % (imdb.score, config['min_score']))
            if 'min_votes' in config:
                if imdb.votes < config['min_votes']:
                    reasons.append('min_votes (%s < %s)' % (imdb.votes, config['min_votes']))
            if 'min_year' in config:
                if imdb.year < config['min_year']:
                    reasons.append('min_year')
            if 'reject_genres' in config:
                rejected = config['reject_genres']
                for genre in imdb.genres:
                    if genre in rejected:
                        reasons.append('reject_genres')
                        break
            if 'reject_languages' in config:
                rejected = config['reject_languages']
                for language in imdb.languages:
                    if language in rejected:
                        reasons.append('relect_languages')
                        break
            if 'accept_languages' in config:
                accepted = config['accept_languages']
                for language in imdb.languages:
                    if language not in accepted:
                        reasons.append('accept_languages')
                        break

            # populate some fields from imdb results, incase someone wants to use them later
            entry['imdb_plot_outline'] = imdb.plot_outline
            entry['imdb_name'] = imdb.name

            if reasons:
                log_once('Rejecting %s because of rule(s) %s' % (entry['title'], ', '.join(reasons)), log)
                feed.reject(entry, ', '.join(reasons))
            else:
                log.debug('Accepting %s' % (entry))
                feed.accept(entry)

            # give imdb a little break between requests (see: http://flexget.com/ticket/129#comment:1)
            if not feed.manager.options.debug:
                import time
                time.sleep(3)