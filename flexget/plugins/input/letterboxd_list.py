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
base_url = 'http://letterboxd.com'

P_SLUGS = {
    'diary': '/%s/films/diary/',
    'likes': '/%s/likes/films/',
    'rated': '/%s/films/ratings/',
    'watched': '/%s/films/',
    'watchlist': '/%s/watchlist/',
    'other': '/%s/list/%s/'
}

M_SLUGS = {
    'diary': 'data-film-slug',
    'likes': 'data-film-link',
    'rated': 'data-film-slug',
    'watched': 'data-film-slug',
    'watchlist': 'data-film-slug',
    'other': 'data-film-slug'
}

LOG_STR = {
    'diary': 'Retrieving %s\'s film diary from Letterboxd.',
    'likes': 'Retrieving list of films %s has liked on Letterboxd.',
    'rated': 'Retrieving list of films rated by %s on Letterboxd.',
    'watched': 'Retrieving list of films watched by %s from Letterboxd.',
    'watchlist': 'Retrieving %s\'s watchlist from Letterboxd.',
    'other': 'Retrieving %s\'s Letterboxd list: %s.'
}

SORT_BY = {
    'added': 'by/added/',
    'length-ascending': 'by/shortest/',
    'length-descending': 'by/longest/',
    'name': 'by/name/',
    'popularity': 'by/popular/',
    'rating-ascending': 'by/rating-lowest/',
    'rating-descending': 'by/rating/',
    'release-ascending': 'by/release-earliest/',
    'release-descending': 'by/release/'
}

class LetterboxdList(object):

    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'list': {'type': 'string'},
            'sort_by': {'type': 'string', 'enum': list(SORT_BY.keys())},
            'max_pages': {'type': 'integer'}
        },
        'required': ['username', 'list'],
        'addditionalProperties': False
    }

    @cached('letterboxd_list', persist='2 hours')

    def on_task_input(self, task, config):        
        m_list = config['list'].lower().replace(' ', '-')
        max_pages = config.get('max_pages', 1)
        pagecount = 0
        next_page = ''
        sort_by = ''
        
        if m_list in list(P_SLUGS.keys()):
            p_slug = P_SLUGS.get(m_list) % config['username']
            m_slug = M_SLUGS.get(m_list)
            log.verbose(LOG_STR.get(m_list) % config['username'])
        else:
            p_slug = P_SLUGS.get('other') % (config['username'], m_list)
            m_slug = M_SLUGS.get('other')
            log.verbose(LOG_STR.get('other') % (config['username'], m_list))
        
        if 'sort_by' in config:
            sort_by = SORT_BY.get(config['sort_by'])

        url = base_url + p_slug + sort_by
        entries = []

        while next_page is not None and pagecount < max_pages:

            try:
                page = task.requests.get(url).content
            except RequestException as e:
                raise plugin.PluginError('Can\'t retrieve Letterboxd list from %s. Make sure it\'s not set to private, and check your config.' % url)
            soup = get_soup(page)

            for movie in soup.find_all(attrs={m_slug: True}):
                m_url = base_url + movie.get(m_slug)
                try:
                    m_page = task.requests.get(m_url).content
                except RequestException:
                    continue
                m_soup = get_soup(m_page)                

                entry = Entry()
                entry['title'] = m_soup.find(property='og:title').get('content')
                entry['url'] = m_url
                entry['imdb_id'] = extract_id(m_soup.find(href=re.compile('imdb')).get('href'))
                entry['tmdb_id'] = re.search(r'\/(\d+)\/$', m_soup.find(href=re.compile('themoviedb')).get('href')).group(1)
                entry['letterboxd_list'] = '%s (%s)' % (m_list, config['username'])
                try:
                    entry['letterboxd_score'] = float(m_soup.find(itemprop='average').get('content'))
                except AttributeError:
                    pass
                if m_list in ['diary', 'rated']:
                    try:
                        entry['letterboxd_score'] = float(movie.find_next(itemprop='rating').get('content'))
                    except AttributeError:
                        pass
                entries.append(entry)

            next_page = soup.find(class_='paginate-next')
            if next_page is not None:
                next_page = next_page.get('href')
                url = base_url + next_page
            if 'max_pages' in config:
                pagecount += 1

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(LetterboxdList, 'letterboxd_list', api_ver=2)
