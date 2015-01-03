from __future__ import unicode_literals, division, absolute_import
import logging

from requests import RequestException

from flexget import plugin
from flexget.event import event
from flexget.utils import json
from flexget.utils.trakt import API_URL, get_entry_ids, get_session, make_list_slug


class TraktSubmit(object):

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
    remove = None
    log = None

    @plugin.priority(-255)
    def on_task_output(self, task, config):
        """Submits accepted movies or episodes to trakt api."""
        found = {'shows': [], 'movies': []}
        for entry in task.accepted:
            if 'series_name' in entry:
                show = {'title': entry['series_name'], 'ids': get_entry_ids(entry)}
                if 'series_season' in entry:
                    season = {'number': entry['series_season']}
                    if 'series_episode' in entry:
                        season['episodes'] = [{'number': entry['series_episode']}]
                    show['seasons'] = [season]
                found['shows'].append(show)
            elif any(field in entry for field in ['imdb_id', 'tmdb_id', 'movie_name']):
                movie = {'ids': get_entry_ids(entry)}
                if not movie['ids']:
                    movie['title'] = entry.get('movie_name') or entry.get('imdb_name')
                    movie['year'] = entry.get('movie_year') or entry.get('imdb_year')
                found['movies'].append(movie)

        if not (found['shows'] or found['movies']):
            self.log.debug('Nothing to submit to trakt.')
            return

        if config['list'] in ['collection', 'watchlist', 'watched']:
            endpoint = 'sync/%s' % ('history' if config['list'] == 'watched' else config['list'])
        else:
            endpoint = 'users/%s/lists/%s/items' % (config['username'], make_list_slug(config['list']))
        if self.remove:
            endpoint += '/remove'
        url = API_URL + endpoint

        if task.manager.options.test:
            self.log.info('Not submitting to trakt.tv because of test mode.')
            return
        session = get_session(config['username'], config['password'])
        self.log.debug('Submitting data to trakt.tv (%s): %s' % (url, found))
        try:
            result = session.post(url, data=json.dumps(found), raise_status=False)
        except RequestException as e:
            self.log.error('Error submitting data to trakt.tv: %s' % e)
            return
        if 200 <= result.status_code < 300:
            self.log.info('Data successfully sent to trakt.tv')
            self.log.debug('trakt response: ' + result.text)
            # TODO: Improve messages about existing and unknown results
        elif result.status_code == 404:
            self.log.error('List does not appear to exist on trakt: %s' % config['list'])
        elif result.status_code == 401:
            self.log.error('Authentication error: check your trakt.tv username/password')
            self.log.debug('trakt response: ' + result.text)
        else:
            self.log.error('Unknown error submitting data to trakt.tv: %s' % result.text)


class TraktAdd(TraktSubmit):
    """Add all accepted elements in your trakt.tv watchlist/library/seen or custom list."""
    remove = False
    log = logging.getLogger('trakt_add')


class TraktRemove(TraktSubmit):
    """Remove all accepted elements from your trakt.tv watchlist/library/seen or custom list."""
    remove = True
    log = logging.getLogger('trakt_remove')


@event('plugin.register')
def register_plugin():
    plugin.register(TraktAdd, 'trakt_add', api_ver=2)
    plugin.register(TraktRemove, 'trakt_remove', api_ver=2)
