from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.utils.requests import RequestException, Session
from flexget.utils.soup import get_soup

requests = Session(max_retries=5)
requests.set_domain_delay('letterboxd.com', '1 seconds')
base_url = 'http://letterboxd.com'


class LetterboxdSubmit(object):

    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'list': {'type': 'string'}
        },
        'required': ['username', 'password', 'list'],
        'additionalProperties': False
    }

    # Defined by subclasses
    add = None
    remove = None
    log = None


    def parse_film(self, search):
        url = base_url + '/search/%s/' % search
        soup = get_soup(requests.get(url).content)
        film = soup.find(attrs={'data-film-link': True})
        if film is not None:
            film = film.get('data-film-link')

        return film


    def on_task_output(self, task, config):
        requests.get(base_url)
        token = requests.cookies['com.xk72.webparts.csrf']
        params = {'__csrf': token}
        auth = {
            'username': config['username'],
            'password': config['password'],
            'remember': True
        }
        headers = {'Referer': base_url}
        r = requests.post('%s/user/login.do' % base_url, data=dict(params, **auth), headers=headers)

        if self.add:
            for entry in task.accepted:
                if any(field in entry for field in ['imdb_id', 'tmdb_id', 'movie_name']):
                    if 'imdb_id' in entry:
                        film = self.parse_film(entry['imdb_id'])
                        r = requests.post('%s%sremove-from-watchlist/' % (base_url, film), data=params)
                    else:
                        log.warning('No imdb_id found for %s. '  % entry['title'] + \
                                    'This field is required to add entry to Letterboxd.')
                        continue


class LetterboxdAdd(LetterboxdSubmit):
    add = True
    log = logging.getLogger('letterboxd_add')


@event('plugin.register')
def register_plugin():
    plugin.register(LetterboxdAdd, 'letterboxd_add', api_ver=2)
