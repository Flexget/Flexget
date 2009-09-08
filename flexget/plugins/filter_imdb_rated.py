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
        
        Note: in theory this should work on any other page containing imdb urls as well.
    """

    def validator(self):
        from flexget import validator
        return validator.factory('url')

    def update_rated(self, feed):
        """Update my movies list"""
        last_time = feed.simple_persistence.setdefault('last_time', datetime.datetime.now() - datetime.timedelta(hours=5))
        next_time = last_time + datetime.timedelta(hours=4)
        if datetime.datetime.now() < next_time:
            log.debug('skipping my movies update, interval not met. next run at %s' % next_time)
            return
        log.debug('updating my movies from %s' % feed.config['imdb_rated'])
        
        # fix imdb html damnit
        # <td class=list bgcolor="#CCCCCC"} colspan="4">
        #                                 ^ god damn noobs

        massage = [(re.compile('"}'), lambda match: '"')]
        
        data = urllib2.urlopen(feed.config['imdb_rated'])
        soup = BeautifulSoup(data, markupMassage=massage)

        count = 0
        for a_imdb_link in soup.findAll('a', attrs={'href': re.compile('\/title\/tt\d+')}):
            imdb_url = 'http://www.imdb.com%s' % a_imdb_link.get('href')
            
            if not feed.session.query(ImdbRated).filter(ImdbRated.url == feed.config['imdb_rated']).\
                                                 filter(ImdbRated.imdb_url == imdb_url).first():
                rated = ImdbRated(feed.config['imdb_rated'], imdb_url)
                feed.session.add(rated)
                log.debug('adding %s' % rated)
                count += 1
            else:
                log.debug('%s is already stored' % imdb_url)
                
        if count>0:
            log.info('Added %s new movies' % count)

    def feed_filter(self, feed):
        self.update_rated(feed)
        for entry in feed.entries:
            if not 'imdb_url' in entry:
                try:
                    get_plugin_by_name('imdb_lookup').instance.lookup(feed, entry)
                except PluginError:
                    # ignore imdb failures
                    pass
            # still no luck with the imdb url .. skip
            if not 'imdb_url' in entry:
                continue
            if feed.session.query(ImdbRated).filter(ImdbRated.url == feed.config['imdb_rated']).\
                                             filter(ImdbRated.imdb_url == entry['imdb_url']).first():
                feed.reject(entry, 'imdb rated')
                

register_plugin(FilterImdbRated, 'imdb_rated')