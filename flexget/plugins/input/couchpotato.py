from __future__ import unicode_literals, division, absolute_import
from urlparse import urlparse
import logging
from flexget import plugin
from flexget.event import event
from flexget.entry import Entry
from flexget.utils import qualities
from requests import RequestException

log = logging.getLogger('couchpotato')


class CouchPotato(object):
    schema = {
        'type': 'object',
        'properties': {
            'base_url': {'type': 'string'},
            'port': {'type': 'number', 'default': 80},
            'api_key': {'type': 'string'},
            'include_data': {'type': 'boolean', 'default': False}
        },
        'required': ['api_key', 'base_url'],
        'additionalProperties': False
    }

    def on_task_input(self, task, config):
        """Creates an entry for each item in your couchpotato wanted list.

        Syntax:

        couchpotato:
          base_url: <value>
          port: <value> (Default is 80)
          api_key: <value>
          include_data: <value> (Boolean, default is False.

        Options base_url and api_key are required.
        When the include_data property is set to true, the
        """

        parsedurl = urlparse(config.get('base_url'))
        url = '%s://%s:%s%s/api/%s/movie.list?status=active' \
              % (parsedurl.scheme, parsedurl.netloc,
                 config.get('port'), parsedurl.path, config.get('api_key'))
        try:
            json = task.requests.get(url).json()
        except RequestException:
            raise plugin.PluginError('Unable to connect to Couchpotato at %s://%s:%s%s.'
                                     % (parsedurl.scheme, parsedurl.netloc, config.get('port'),
                                        parsedurl.path))
        entries = []

        # Converts quality from CP format to Flexget format
        # TODO: Not all values have exact matches in flexget, need to update flexget qualities

        cp_to_flexget = {'BR-Disk': 'remux',  # Not a perfect match, but as close as currently possible
                         '1080p': '1080p',
                         '720p': '720p',
                         'brrip': 'bluray',
                         'dvdr': 'dvdrip',  # Not a perfect match, but as close as currently possible
                         'dvdrip': 'dvdrip',
                         'scr': 'dvdscr',
                         'r5': 'r5',
                         'tc': 'tc',
                         'ts': 'ts',
                         'cam': 'cam'}

        # Gets profile and quality lists if include_data is TRUE
        if config.get('include_data'):
            profile_url = '%s://%s:%s%s/api/%s/profile.list' \
                          % (parsedurl.scheme, parsedurl.netloc,
                             config.get('port'), parsedurl.path, config.get('api_key'))
            try:
                profile_json = task.requests.get(profile_url).json()
            except RequestException as e:
                raise plugin.PluginError('Unable to connect to Couchpotato at %s://%s:%s%s. Error: %s'
                                         % (parsedurl.scheme, parsedurl.netloc, config.get('port'),
                                            parsedurl.path, e))

        for movie in json['movies']:
            quality = ''
            if movie['status'] == 'active':
                if config.get('include_data'):
                    for profile in profile_json['list']:
                        if profile['_id'] == movie['profile_id']:  # Matches movie profile with profile JSON
                            # Creates a string of flexget qualities from CP's qualities list
                            converted_list = ', '.join([cp_to_flexget[quality] for quality in profile['qualities']])
                            try:
                                quality = qualities.Quality(converted_list)  # Return the best components from the list
                            except ValueError as e:
                                log.debug(e)
                title = movie["title"]
                imdb = movie['info'].get('imdb')
                tmdb = movie['info'].get('tmdb_id')
                entry = Entry(title=title,
                              url='',
                              imdb_id=imdb,
                              tmdb_id=tmdb,
                              quality=quality)
                if entry.isvalid():
                    entries.append(entry)
                else:
                    log.error('Invalid entry created? %s' % entry)
                # Test mode logging
                if entry and task.options.test:
                    log.info("Test mode. Entry includes:")
                    log.info("    Title: %s" % entry["title"])
                    log.info("    URL: %s" % entry["url"])
                    log.info("    IMDB ID: %s" % entry["imdb_id"])
                    log.info("    TMDB ID: %s" % entry["tmdb_id"])
                    log.info("    Quality: %s" % entry["quality"])
                    continue
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(CouchPotato, 'couchpotato', api_ver=2)
