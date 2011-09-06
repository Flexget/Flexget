import logging
import hashlib
import urllib2
from flexget.plugin import register_plugin, DependencyError
from flexget.utils.tools import urlopener

try:
    import simplejson as json
except ImportError:
    try:
        import json
    except ImportError:
        raise DependencyError(issued_by='trakt_acquired', missing='simplejson', message='trakt_acquired requires either '
                'simplejson module or python > 2.5')

log = logging.getLogger('trakt_acquired')


class TraktAcquired(object):
    """Marks all accepted TV episodes or movies as acquired in your trakt.tv library."""

    def validator(self):
        from flexget import validator
        root = validator.factory('dict')
        root.accept('text', key='username', required=True)
        root.accept('text', key='password', required=True)
        root.accept('text', key='api_key', required=True)
        root.accept('choice', key='type', required=True).accept_choices(['movies', 'series'])
        return root

    def on_feed_exit(self, feed, config):
        """Finds accepted movies and series episodes and submits them to trakt as acquired."""
        # Change password to an SHA1 digest of the password
        config['password'] = hashlib.sha1(config['password']).hexdigest()
        found = {}
        for entry in feed.accepted:
            if config['type'] == 'series':
                # Check entry is a series episode
                if entry.get('series_name') and entry.get('series_season') and entry.get('series_episode'):
                    series = found.setdefault(entry['series_name'], {})
                    if not series:
                        # If this is the first episode found from this series, set the parameters
                        series['title'] = entry.get('series_name_tvdb', entry['series_name'])
                        if entry.get('imdb_id'):
                            series['imdb_id'] = entry['imdb_id']
                        if entry.get('thetvdb_id'):
                            series['tvdb_id'] = entry['thetvdb_id']
                        series['episodes'] = []
                    series['episodes'].append({'season': entry['series_season'], 'episode': entry['series_episode']})
                    log.debug('Marking %s S%02dE%02d for submission to trakt.tv library.' % (entry['series_name'], entry['series_season'], entry['series_episode']))
            else:
                # Check entry is a movie
                if entry.get('imdb_id') or entry.get('tmdb_id'):
                    movie = {}
                    # We know imdb_id or tmdb_id is filled in, so don't cause any more lazy lookups
                    if entry.get('movie_name', lazy=False):
                        movie['title'] = entry['movie_name']
                    if entry.get('movie_year', lazy=False):
                        movie['year'] = entry['movie_year']
                    if entry.get('tmdb_id', lazy=False):
                        movie['tmdb_id'] = entry['tmdb_id']
                    if entry.get('imdb_id', lazy=False):
                        movie['imdb_id'] = entry['imdb_id']
                    # We use an extra container dict so that the found dict is usable in the same way as found series
                    found.setdefault('movies', {}).setdefault('movies', []).append(movie)
                    log.debug('Marking %s for submission to trakt.tv library.' % entry['title'])

        if feed.manager.options.test:
            log.info('Not submitting to trakt.tv because of test mode.')
            return

        # Submit our found items to trakt
        if config['type'] == 'series':
            post_url = 'http://api.trakt.tv/show/episode/library/' + config['api_key']
        else:
            post_url = 'http://api.trakt.tv/movie/library/' + config['api_key']
        for item in found.itervalues():
            # Add username and password to the dict to submit
            item.update({'username': config['username'], 'password': config['password']})
            try:
                self.post_json_to_trakt(post_url, item)
            except urllib2.URLError, e:
                log.error('Error submitting data to trakt.tv: %s' % e)
                continue
                
    def post_json_to_trakt(self, url, data):
        """Dumps data as json and POSTs it to the specified url."""
        req = urllib2.Request(url, json.dumps(data), {'content-type': 'application/json'})
        return urlopener(req, log)


register_plugin(TraktAcquired, 'trakt_acquired', api_ver=2)
