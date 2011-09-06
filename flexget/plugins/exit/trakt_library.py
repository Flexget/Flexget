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
        raise DependencyError(issued_by='trakt_library', missing='simplejson', message='trakt_library requires either '
                'simplejson module or python > 2.5')

log = logging.getLogger('trakt_library')


class TraktLibrary(object):
    """Marks all accepted TV episodes or movies as acquired in your trakt.tv library."""

    def validator(self):
        from flexget import validator
        root = validator.factory('dict')
        root.accept('text', key='username', required=True)
        root.accept('text', key='password', required=True)
        root.accept('text', key='api_key', required=True)
        return root

    def on_feed_exit(self, feed, config):
        """Finds accepted movies and series episodes and submits them to trakt as acquired."""
        # Change password to an SHA1 digest of the password
        config['password'] = hashlib.sha1(config['password']).hexdigest()
        found_series = {}
        found_movies = {}
        for entry in feed.accepted:
            # Check if it is a series
            if entry.get('series_name') and entry.get('series_season') and entry.get('series_episode'):
                series = found_series.setdefault(entry['series_name'], {})
                if not series:
                    # If this is the first episode found from this series, set the parameters
                    series['username'] = config['username']
                    series['password'] = config['password']
                    series['title'] = entry.get('series_name_tvdb', entry['series_name'])
                    if entry.get('imdb_id'):
                        series['imdb_id'] = entry['imdb_id']
                    if entry.get('thetvdb_id'):
                        series['tvdb_id'] = entry['thetvdb_id']
                    series['episodes'] = []
                series['episodes'].append({'season': entry['series_season'], 'episode': entry['series_episode']})
                log.debug('Marking %s S%02dE%02d for submission to trakt.tv library.' % (entry['series_name'], entry['series_season'], entry['series_episode']))

            #TODO: Check if it is a movie

        if feed.manager.options.test:
            log.info('Not submitting to trakt.tv because of test mode.')
            return

        # Submit our found series to trakt
        post_url = 'http://api.trakt.tv/show/episode/library/' + config['api_key']
        for series in found_series.itervalues():
            try:
                self.post_json_to_trakt(post_url, series)
            except urllib2.URLError, e:
                log.error('Error submitting series data to trakt.tv: %s' % e)
                continue

        #TODO: Submit the found movies to trakt
                
    def post_json_to_trakt(self, url, data):
        """Dumps data as json and POSTs it to the specified url."""
        req = urllib2.Request(url, json.dumps(data), {'content-type': 'application/json'})
        return urlopener(req, log)


register_plugin(TraktLibrary, 'trakt_library', api_ver=2)
