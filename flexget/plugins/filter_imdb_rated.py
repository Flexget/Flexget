import logging
from flexget.plugin import *
from BeautifulSoup import BeautifulSoup
from flexget.manager import Base
from sqlalchemy import Table, Column, Integer, Float, String, DateTime
import urllib2
import re
import datetime

log = logging.getLogger('imdb_rated')

class ImdbRated(Base):

    __tablename__ = 'imdb_rated'

    id = Column(Integer, primary_key=True)
    url = Column(String)
    imdb_url = Column(String)
    score = Column(Float)
    added = Column(DateTime)

    def __init__(self, url, imdb_url):
        self.url = url
        self.imdb_url = imdb_url
        self.added = datetime.datetime.now()

    def __str__(self):
        return '<ImdbRated(%s at %s)>' % (self.imdb_url, self.url)

class FilterImdbRated:
    """
        Reject already voted entries based on user imdb vote history.
        
        Example:
        
        imdb_rated: http://www.imdb.com/mymovies/list?l=<YOUR USER ID>
        
        Reverse, reject unvoted:
        
        Example:
        
        imdb_rated:
          url: http://www.imdb.com/mymovies/list?l=<YOUR USER ID>
          reverse: yes
        
        Note: in theory this should work with any other page containing imdb urls.
    """

    def validator(self):
        from flexget import validator
        root =  validator.factory()
        root.accept('url')
        complex = root.accept('dict')
        complex.accept('url', key='url')
        complex.accept('boolean', key='reverse')
        return root

    def update_rated(self, feed, config):
        """Update my movies list"""
        # set first last_time into past so we trigger update on first run
        next_time = feed.simple_persistence.setdefault('next_time', datetime.datetime.min)
        log.debug('next_time: %s' % next_time)
        if not datetime.datetime.now() > next_time:
            return
        feed.simple_persistence.set('next_time', datetime.datetime.now() + datetime.timedelta(hours=4))
        log.debug('updating my movies from %s' % config['url'])
        
        # fix imdb html damnit
        # <td class=list bgcolor="#CCCCCC"} colspan="4">
        #                                 ^ god damn noobs

        massage = [(re.compile('"}'), lambda match: '"')]
        
        data = urllib2.urlopen(config['url'])
        soup = BeautifulSoup(data, markupMassage=massage)

        count = 0
        for a_imdb_link in soup.findAll('a', attrs={'href': re.compile('\/title\/tt\d+')}):
            imdb_url = 'http://www.imdb.com%s' % a_imdb_link.get('href')
            
            if not feed.session.query(ImdbRated).filter(ImdbRated.url == config['url']).\
                                                 filter(ImdbRated.imdb_url == imdb_url).first():
                rated = ImdbRated(config['url'], imdb_url)
                feed.session.add(rated)
                log.debug('adding %s' % rated)
                count += 1
                
        if count > 0:
            log.info('Added %s new movies' % count)

    def on_feed_filter(self, feed):
        config = feed.config['imdb_rated']
        if isinstance(config, basestring):
            config = {}
            config['url'] = feed.config['imdb_rated']
        
        self.update_rated(feed, config)
        for entry in feed.entries:
            
            # if no imdb_url perform lookup
            if not 'imdb_url' in entry:
                try:
                    get_plugin_by_name('imdb_lookup').instance.lookup(feed, entry)
                except PluginError:
                    pass # ignore imdb lookup failures

            # ignore entries without imdb_url
            if not 'imdb_url' in entry:
                continue
            
            is_rated = feed.session.query(ImdbRated).\
                       filter(ImdbRated.url == config['url']).\
                       filter(ImdbRated.imdb_url == entry['imdb_url']).first() is not None
                       
            if config.get('reverse', False):
                # reversed, reject unrated
                if not is_rated:
                    feed.reject(entry, 'imdb rated reverse')
            else:
                # normal mode, reject rated
                if is_rated: 
                    feed.reject(entry, 'imdb rated')
                

register_plugin(FilterImdbRated, 'imdb_rated')