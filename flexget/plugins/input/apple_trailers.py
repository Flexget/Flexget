from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import re

import feedparser
from requests.auth import AuthBase

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.utils.requests import RequestException

log = logging.getLogger('apple_trailers')


class AppleTrailers(object):
    """
        Adds support for Apple.com movie trailers.

        Configuration:
        quality: Set the desired resolution - 480p, 720p or 1080p. default '720p'
        genres:  List of genres used to filter the entries. If set, the
        trailer must match at least one listed genre to be accepted. Genres
        that can be used: Action and Adventure, Comedy, Documentary, Drama,
        Family, Fantasy, Foreign, Horror, Musical, Romance, Science Fiction,
        Thriller. default '' (all)

        apple_trailers:
          quality: 720p
          genres: ['Action and Adventure']

        Alternatively, a simpler configuration format can be used. This uses
        the default genre filter, all:

        apple_trailers: 720p

        This plugin adds the following fields to the entry:
          movie_name, movie_year, genres, apple_trailers_name, movie_studio
        movie_name: Name of the movie
        movie_year: Year the movie was/will be released
        genres: Comma-separated list of genres that apply to the movie
        apple_trailers_name: Contains the Apple-supplied name of the clip,
        such as 'Clip 2', 'Trailer', 'Winter Olympic Preview'
        movie_studio: Name of the studio that makes the movie
    """

    movie_data_url = 'http://trailers.apple.com/trailers/feeds/data/'
    rss_url = 'http://trailers.apple.com/trailers/home/rss/newtrailers.rss'
    qualities = {'480p': 'sd', '720p': 'hd720', '1080p': 'hd1080'}

    schema = {
        'oneOf': [
            {
                'type': 'object',
                'properties': {
                    'quality': {
                        'type': 'string',
                        'enum': list(qualities.keys()),
                        'default': '720p',
                    },
                    'genres': {'type': 'array', 'items': {'type': 'string'}},
                },
                'additionalProperties': False,
            },
            {'title': 'justquality', 'type': 'string', 'enum': list(qualities.keys())},
        ]
    }

    def broken(self, error_message):
        raise plugin.PluginError('Plugin is most likely broken. Got: %s' % error_message)

    @plugin.priority(127)
    @cached('apple_trailers')
    def on_task_input(self, task, config):
        # Turn simple config into full config
        if isinstance(config, str):
            config = {'quality': config}

        try:
            r = task.requests.get(self.rss_url)
        except RequestException as e:
            raise plugin.PluginError('Retrieving Apple Trailers RSS feed failed: %s' % e)

        rss = feedparser.parse(r.content)

        if rss.get('bozo_exception', False):
            raise plugin.PluginError('Got bozo_exception (bad feed)')

        filmid_regex = re.compile('(FilmId\s*\=\s*\')(\d+)(?=\')')
        studio_regex = re.compile('(?:[0-9]*\s*)(.+)')
        # use the following dict to save json object in case multiple trailers have been released for the same movie
        # no need to do multiple requests for the same thing!
        trailers = {}
        entries = []
        for item in rss.entries:
            entry = Entry()
            movie_url = item['link']
            entry['title'] = item['title']
            entry['movie_name'], entry['apple_trailers_name'] = entry['title'].split(' - ', 1)
            if not trailers.get(movie_url):
                try:
                    movie_page = task.requests.get(movie_url).text
                    match = filmid_regex.search(movie_page)
                    if match:
                        json_url = self.movie_data_url + match.group(2) + '.json'
                        movie_data = task.requests.get(json_url).json()

                        trailers[movie_url] = {'json_url': json_url, 'json': movie_data}
                    else:
                        self.broken('FilmId not found for {0}'.format(entry['movie_name']))

                except RequestException as e:
                    log.error('Failed to get trailer %s: %s', entry['title'], e.args[0])
                    continue
            else:
                movie_data = trailers[movie_url]['json']
            genres = {genre.get('name') for genre in movie_data.get('details').get('genres')}
            config_genres = set(config.get('genres', []))
            if genres and config_genres and not set.intersection(config_genres, genres):
                log.debug('Config genre(s) do not match movie genre(s)')
                continue

            desired_quality = config['quality']
            # find the trailer url
            for clip in movie_data.get('clips'):
                if clip.get('title') == entry['apple_trailers_name']:
                    try:
                        trailer_url = clip['versions']['enus']['sizes'][
                            self.qualities[desired_quality]
                        ]
                        src = trailer_url.get('src')
                        src_alt = trailer_url.get('srcAlt')
                        # .mov tends to be a streaming video file, but the real video file is the same url, but
                        # they prepend 'h' to the quality
                        if src.split('.')[-1] == 'mov':
                            entry['url'] = src.replace(desired_quality, 'h' + desired_quality)
                        elif src_alt.split('.')[-1] == 'mov':
                            entry['url'] = src_alt.replace(desired_quality, 'h' + desired_quality)
                        else:
                            continue  # just continue until we reach the else part of the for-else
                        break
                    except KeyError as e:
                        self.broken(e.args[0])
            else:
                log.error('Trailer "%s" not found', entry['apple_trailers_name'])
                continue

            # set some entry fields if present
            # studio is usually also the copyright holder
            studio = studio_regex.match(movie_data.get('page').get('copyright'))
            if studio:
                entry['movie_studio'] = studio.group(1)

            release_date = movie_data.get('page').get('release_date')
            if release_date:
                entry['release_date'] = release_date

            if genres:
                entry['genres'] = ', '.join(list(genres))

            # set the correct header without modifying the task.requests obj
            entry['download_auth'] = AppleTrailersHeader()
            entries.append(entry)

        return entries


class AppleTrailersHeader(AuthBase):
    def __call__(self, request):
        request.headers['User-Agent'] = 'QuickTime/7.7'
        return request


@event('plugin.register')
def register_plugin():
    plugin.register(AppleTrailers, 'apple_trailers', api_ver=2)
