from __future__ import unicode_literals, division, absolute_import
import logging
import re

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.utils.imdb import extract_id
from flexget.utils.requests import RequestException
from flexget.utils.soup import get_soup

log = logging.getLogger('letterboxd_list')


class LetterboxdList(object):

    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'list': {'type': 'string'},
            'maxpages': {'type': 'integer'}
        },
        'required': ['username', 'list'],
        'addditionalProperties': False
    }

    @cached('letterboxd_list', persist='2 hours')
    def on_task_input(self, task, config):        
        base_url = 'http://letterboxd.com'
        list = config['list'].lower().replace(' ', '-')
        maxpages = config.get('maxpages', 1)

        if list == 'watchlist':
            next_page = '/%s/watchlist/' % config['username']
            m_slug = 'data-film-slug'
            log.verbose('Retrieving %s\'s watchlist from Letterboxd.' % config['username'])
        elif list == 'diary':
            next_page = '/%s/films/diary/' % config['username']
            m_slug = 'data-film-link'
            log.verbose('Retrieving %s\'s film diary from Letterboxd.' % config['username'])
        elif list == 'likes':
            next_page = '/%s/likes/films/' % config['username']
            m_slug = 'data-film-link'
            log.verbose('Retrieving list of films %s has liked on Letterboxd.' % config['username'])
        else:
            next_page =  '/%s/list/%s/' % (config['username'], list)
            m_slug = 'data-film-slug'
            log.verbose('Retrieving %s\'s Letterboxd list: %s.' % (config['username'], list))

        pagecount = 0
        entries = []
        while next_page is not None and pagecount < maxpages:
            url = base_url + next_page
            try:
                page = task.requests.get(url)
            except RequestException as e:
                raise plugin.PluginError('Can\'t retrieve Letterboxd list. If it\'s not set to private, it may not exist. Check your config.')
            soup = get_soup(page.text)
            if list == 'diary':
                movies = soup.find_all('tr', attrs={'class': 'diary-entry-row'})
            else:
                movies = soup.find_all('li', attrs={'class': 'poster-container'})

            for movie in movies:
                if list == 'diary':
                    m_url = base_url + movie.find('td', attrs={'class': 'td-actions'}).get(m_slug)
                    try:
                        user_rating = movie.find('meta', attrs={'itemprop': 'rating'}).get('content')
                    except AttributeError:
                        pass
                else:
                    m_url = base_url + movie.find('div').get(m_slug)
                m_page = task.requests.get(m_url)
                m_soup = get_soup(m_page.text)
                
                entry = Entry()
                title = m_soup.find('section', attrs={'id': 'featured-film-header'}).find('h1').string
                year = m_soup.find('section', attrs={'id': 'featured-film-header'}).find('small').string
                entry['title'] = '%s (%s)' % (title, year)
                entry['url'] = m_url
                imdb_url = m_soup.find('p', attrs={'class': 'text-link'}).find(href=re.compile('imdb')).get('href')
                entry['imdb_id'] = extract_id(imdb_url)
                tmdb_url = m_soup.find('p', attrs={'class': 'text-link'}).find(href=re.compile('themoviedb'))
                entry['tmdb_id'] = re.search(r'\/(\d+)\/$', tmdb_url.get('href')).group(1)
                entry['letterboxd_list'] = '%s (%s)' % (list, config['username'])
                entry['letterboxd_score'] = 0
                if list == 'diary' and user_rating:
                    entry['letterboxd_score'] = user_rating
                else:
                    entry['letterboxd_score'] = m_soup.find('span', attrs={'class': 'average-rating'})\
                    .find('meta', attrs={'itemprop': 'average'}).get('content')                
                entries.append(entry)

            next_page = soup.find('a', attrs={'class': 'paginate-next'})
            if next_page is not None:
                next_page = next_page.get('href')
            if config['maxpages']:
                pagecount += 1

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(LetterboxdList, 'letterboxd_list', api_ver=2)
