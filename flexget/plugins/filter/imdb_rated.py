from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.plugin import register_plugin, PluginWarning, PluginError, get_plugin_by_name
from bs4 import BeautifulSoup
from flexget.manager import Base
from sqlalchemy import Column, Integer, Float, String, DateTime
import re
import datetime
from flexget.utils.tools import urlopener

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


class FilterImdbRated(object):
    """
    Reject already voted entries based on user imdb vote history.

    Example::

      imdb_rated: http://www.imdb.com/mymovies/list?l=<YOUR USER ID>

    Reverse, reject unvoted::

      imdb_rated:
        url: http://www.imdb.com/mymovies/list?l=<YOUR USER ID>
        reverse: yes

    Note: in theory this should work with any other page containing imdb urls.
    """

    schema = {
        'type': ['string', 'object'],
        'format': 'url',
        'properties': {
            'url': {'type': 'string', 'format': 'url'},
            'reverse': {'type': 'boolean'}
        },
        'required': ['url']
    }

    def update_rated(self, task, config):
        """Update my movies list"""
        # set first last_time into past so we trigger update on first run
        next_time = task.simple_persistence.setdefault('next_time', datetime.datetime.min)
        log.debug('next_time: %s' % next_time)
        if not datetime.datetime.now() > next_time:
            return
        task.simple_persistence['next_time'] = datetime.datetime.now() + datetime.timedelta(hours=4)
        log.debug('updating my movies from %s' % config['url'])

        massage = []

        # fix imdb html, just enough to pass parser
        #
        # <td class=list bgcolor="#CCCCCC"} colspan="4">
        #                                 ^ god damn noobs

        massage.append((re.compile('"}'), lambda match: '"'))

        # onclick="(new Image()).src='/rg/home/navbar/images/b.gif?link=/'"">IMDb</a>
        #                                                                 ^ are you even trying?

        massage.append((re.compile('/\'""'), lambda match: '/\'"'))

        # <table class="footer" id="amazon-affiliates"">
        #                                             ^ ffs, I don't think they are even trying ...

        massage.append((re.compile('amazon-affiliates""'), lambda match: 'amazon-affiliates"'))

        data = urlopener(config['url'], log)
        soup = BeautifulSoup(data)

        count = 0
        for a_imdb_link in soup.find_all('a', attrs={'href': re.compile(r'/title/tt\d+')}):
            imdb_url = 'http://www.imdb.com%s' % a_imdb_link.get('href')

            if not task.session.query(ImdbRated).filter(ImdbRated.url == config['url']).\
                    filter(ImdbRated.imdb_url == imdb_url).first():
                rated = ImdbRated(config['url'], imdb_url)
                task.session.add(rated)
                log.debug('adding %s' % rated)
                count += 1

        if count > 0:
            log.info('Added %s new movies' % count)

    def on_task_filter(self, task):
        raise PluginWarning('This plugin no longer works with the imdb, replacement will be implemented soon')

        config = task.config['imdb_rated']
        if isinstance(config, basestring):
            config = {'url': task.config['imdb_rated']}

        self.update_rated(task, config)
        for entry in task.entries:

            # if no imdb_url perform lookup
            if not 'imdb_url' in entry:
                try:
                    get_plugin_by_name('imdb_lookup').instance.lookup(entry)
                except PluginError:
                    pass # ignore imdb lookup failures

            # ignore entries without imdb_url
            if not 'imdb_url' in entry:
                continue

            is_rated = task.session.query(ImdbRated).\
                filter(ImdbRated.url == config['url']).\
                filter(ImdbRated.imdb_url == entry['imdb_url']).first() is not None

            if config.get('reverse', False):
                # reversed, reject unrated
                if not is_rated:
                    entry.reject('imdb rated reverse')
            else:
                # normal mode, reject rated
                if is_rated:
                    entry.reject('imdb rated')


register_plugin(FilterImdbRated, 'imdb_rated')
