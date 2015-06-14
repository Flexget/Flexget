from __future__ import unicode_literals, division, absolute_import
import logging
import re

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.utils.requests import RequestException, Session

requests = Session(max_retries=5)
requests.set_domain_delay('letterboxd.com', '1 seconds')
base_url = 'http://letterboxd.com'


LISTS = {
    'watchlist': {
        'add_command': 'add-to-watchlist',
        'remove_command': 'remove-from-watchlist',
        'add_log': 'Added film to your Letterboxd watchlist: %s',
        'remove_log': 'Removed film from your Letterboxd watchlist: %s'},
    'watched': {
        'add_command': 'mark-as-watched',
        'remove_command': 'mark-as-not-watched',
        'add_log': 'Marked film as seen on Letterboxd: %s',
        'remove_log': 'Marked film as not seen on Letterboxd: %s'}
}


class LetterboxdSubmit(object):

    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'list': {'type': 'string', 'enum': list(LISTS.keys())}
        },
        'required': ['username', 'password', 'list'],
        'additionalProperties': False
    }



    # Defined by subclasses
    add = None
    remove = None
    log = None


    def parse_film(self, search):
        url = base_url + '/search/films/%s/' % search
        film = re.search(r'\/film\/(.*?)\/', requests.get(url).content).group(1)

        return film


    def on_task_output(self, task, config):
        requests.get(base_url)
        token = requests.cookies['com.xk72.webparts.csrf']
        params = {'__csrf': token}
        auth = {
            'username': config['username'],
            'password': config['password'],
        }
        headers = {'Referer': base_url}
        r = requests.post('%s/user/login.do' % base_url,
                          data=dict(params, **auth), headers=headers, raise_status=False)

        if self.add:
            command = LISTS[config['list']]['add_command']
            log_str = LISTS[config['list']]['add_log']
        elif self.remove:
            command = LISTS[config['list']]['remove_command']
            log_str = LISTS[config['list']]['remove_log']

        for entry in task.accepted:
            if any(field in entry for field in ['imdb_id', 'tmdb_id', 'movie_name']):
                if 'imdb_id' in entry:
                    film = self.parse_film(entry['imdb_id'])
                    try:
                        r = requests.post('%s/film/%s/%s/' % (base_url, film, command), data=params)
                    except RequestException as e:
                        self.log.error('Error accessing %s/film/%s/%s/' % (base_url, film, command))
                    if 200 <= r.status_code < 300:
                        self.log.verbose(log_str % entry['title'])
                        self.log.debug('Letterboxd response: %s' % r.text)
                    elif r.status_code == 404:
                        self.log.error('Can\'t access film data at: %s/film/%s' % (base_url, film))
                    elif r.status_code == 401:
                        self.log.error('Authentication error. Check your Letterboxd username and password.')
                        self.log.debug('Letterboxd response: %s' % r.text)
                    else:
                        self.log.error('Unknown error accessing film data on Letterboxd: %s' % r.text)
                else:
                    log.warning('No imdb_id found for %s. '  % entry['title'] + \
                                'This field is required to add entry to Letterboxd.')
                    continue


class LetterboxdAdd(LetterboxdSubmit):
    add = True
    log = logging.getLogger('letterboxd_add')


class LetterboxdRemove(LetterboxdSubmit):
    remove = True
    log = logging.getLogger('letterboxd_remove')


@event('plugin.register')
def register_plugin():
    plugin.register(LetterboxdAdd, 'letterboxd_add', api_ver=2)
    plugin.register(LetterboxdRemove, 'letterboxd_remove', api_ver=2)
