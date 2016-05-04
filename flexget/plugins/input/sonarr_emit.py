from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import urlparse

import logging
import math

from requests import RequestException

from flexget import plugin
from flexget.event import event
from flexget.entry import Entry

log = logging.getLogger('sonarr_emit')


class SonarrEmit(object):

    """
    This plugin return the 1st missing episode of every show configures in Sonarr.
    This can be used with the discover plugin or set_series_begin plugin to
    get the relevant data from Sonarr.

    Syntax:

    sonarr_emit:
      base_url=<value> (Required)
      port=<value> (Default is 80)
      api_key=<value> (Required)
      include_ended=<yes|no> (Default is yes)
      only_monitored=<yes|no> (Default is yes)
      page_size=<value> (Default is 50)

    Page size determines the amount of results per each API call.
    Higher value means a bigger response. Lower value means more calls.
    Should be changed if there are performance issues.


    Usage: (Example with discover)

    discover_from_sonarr_task:
      discover:
        what:
          - sonarr_emit:
              base_url: '{{ secrets.credentials.sonarr.url }}'
              port: 8989
              api_key: '{{ secrets.credentials.sonarr.api_key }}'
              include_ended: false
        from:
          - kat:
              verified: yes
      all_series: yes
      download: c:\bla\

    Usage: (Example with set_series_begin)

    set-series-begin-from-sonarr:
      sonarr_emit:
        base_url: '{{ secrets.credentials.sonarr.url }}'
        port: 8989
        api_key: '{{ secrets.credentials.sonarr.api_key }}'
        include_ended: false
      accept_all: yes
      set_series_begin: yes
    """
    schema = {
        'type': 'object',
        'properties': {
            'base_url': {'type': 'string'},
            'port': {'type': 'number', 'default': 80},
            'api_key': {'type': 'string'},
            'include_ended': {'type': 'boolean', 'default': True},
            'only_monitored': {'type': 'boolean', 'default': True},
            'page_size': {'type': 'number', 'default': 50}
        },
        'required': ['api_key', 'base_url'],
        'additionalProperties': False
    }

    # Function that gets a page number and page size and returns the responding result json
    def get_page(self, task, config, page_number):
        parsedurl = urlparse(config.get('base_url'))
        url = '%s://%s:%s%s/api/wanted/missing?page=%d&pageSize=%d&sortKey=series.title&sortdir=asc' \
              % (parsedurl.scheme, parsedurl.netloc, config.get('port'),
                 parsedurl.path, page_number, config.get('page_size'))
        headers = {'X-Api-Key': config['api_key']}
        try:
            json = task.requests.get(url, headers=headers).json()
        except RequestException as e:
            raise plugin.PluginError('Unable to connect to Sonarr at %s://%s:%s%s. Error: %s'
                                     % (parsedurl.scheme, parsedurl.netloc, config.get('port'),
                                        parsedurl.path, e))
        return json

    def on_task_input(self, task, config):
        json = self.get_page(task, config, 1)
        entries = []
        pages = int(math.ceil(json['totalRecords'] / config.get('page_size')))  # Sets number of requested pages
        current_series_id = 0  # Initializes current series parameter
        for page in range(2, pages):
            for record in json['records']:
                if current_series_id != record['seriesId']:
                    current_series_id = record['seriesId']
                    season = record['seasonNumber']
                    episode = record['episodeNumber']
                    entry = Entry(url='',
                                  series_name=record['series']['title'],
                                  series_season=season,
                                  series_episode=episode,
                                  series_id='S%02dE%02d' % (season, episode),
                                  tvdb_id=record['series'].get('tvdbId'),
                                  tvrage_id=record['series'].get('tvRageId'),
                                  tvmaze_id=record['series'].get('tvMazeId'),
                                  title=record['series']['title'] + ' ' + 'S%02dE%02d' % (season, episode))
                    if entry.isvalid():
                        entries.append(entry)
                    else:
                        log.error('Invalid entry created? %s' % entry)
                    # Test mode logging
                    if entry and task.options.test:
                        log.verbose("Test mode. Entry includes:")
                        for key, value in list(entry.items()):
                            log.verbose('     %s: %s' % (key.capitalize(), value))
            json = self.get_page(task, config, page)
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(SonarrEmit, 'sonarr_emit', api_ver=2)
