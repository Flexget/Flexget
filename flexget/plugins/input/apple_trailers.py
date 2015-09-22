from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.utils.requests import RequestException
from flexget.utils.soup import get_soup
try:
    from flexget.plugins.input.rss import InputRSS
except ImportError:
    raise plugin.DependencyError(issued_by='apple_trailers', missing='rss')

log = logging.getLogger('apple_trailers')


class AppleTrailers(InputRSS):
    """
        Adds support for Apple.com movie trailers.

        Configuration:
        quality: Set the desired resolution - 480p or 720p. default '720p'
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

    rss_url = 'http://trailers.apple.com/trailers/home/rss/newtrailers.rss'
    qualities = ['480p', '720p']

    schema = {
        'oneOf': [
            {
                'type': 'object',
                'properties': {
                    'quality': {
                        'type': 'string',
                        'enum': qualities,
                        'default': '720p'
                    },
                    'genres': {'type': 'array', 'items': {'type': 'string'}}
                },
                'additionalProperties': False
            },
            {'title': 'justquality', 'type': 'string', 'enum': qualities}
        ]

    }

    # Run before headers plugin
    @plugin.priority(135)
    def on_task_start(self, task, config):
        # TODO: Resolve user-agent in a way that doesn't involve modifying the task config.
        # make sure we have dependencies available, will throw DependencyError if not
        plugin.get_plugin_by_name('headers')
        # configure them
        task.config['headers'] = {'User-Agent': 'Quicktime/7.7'}

    @plugin.priority(127)
    @cached('apple_trailers')
    def on_task_input(self, task, config):
        # use rss plugin
        # since we have to do 2 page lookups per trailer, use all_entries False to lighten load
        rss_config = {'url': self.rss_url, 'all_entries': False}
        rss_entries = super(AppleTrailers, self).on_task_input(task, rss_config)

        # Multiple entries can point to the same movie page (trailer 1, clip1, etc.)
        trailers = {}
        for entry in rss_entries:
            url = entry['original_url']
            trailers.setdefault(url, []).append(entry['title'])

        result = []
        for url, titles in trailers.iteritems():
            genre_url = url + '#gallery-film-info-details'
            try:
                page = task.requests.get(genre_url)
                soup = get_soup(page.text)
            except RequestException as err:
                log.warning("RequestsException when opening playlist page: %s" % err)

            genres = set()
            genre_head = soup.find(name='dt', text='Genre')
            if not genre_head:
                log.debug('genre(s) not found')
            for genre_name in genre_head.next_sibling.contents:
                if genre_name == ' ' or genre_name == ', ':
                    continue
                genres.add(genre_name.contents[0].string)
                log.debug('genre found: %s' % genre_name.contents[0].string)

            # Turn simple config into full config
            if isinstance(config, basestring):
                config = {'quality': config}

            if config.get('genres'):
                config_genres = set(config.get('genres'))
                good_genres = set.intersection(config_genres, genres)
                if not good_genres:
                    continue

            film_detail = soup.find(class_='film-detail')
            release_year = ''
            studio = ''
            if not film_detail:
                log.debug('film detail not found')
            else:
                release_c = film_detail.contents[1].string
                release_year = release_c[(release_c.find(', 20') + 2):(release_c.find(', 20') + 6)]
                log.debug('release year: %s' % release_year)
                studio_c = film_detail.contents[5].string
                studio = studio_c[7:]
                log.debug('studio: %s' % studio)

            # the HTML for the trailer gallery is stored in a "secret" location...let's see how long this lasts
            # the iPad version has direct links to the video files
            url = url + 'includes/playlists/ipad.inc'
            try:
                page = task.requests.get(url)
                soup = get_soup(page.text)
            except RequestException as err:
                log.warning("RequestsException when opening playlist page: %s" % err)
                continue

            for title in titles:
                log.debug('Searching for trailer title: %s' % title.split(' - ')[1])
                try:
                    trailer = soup.find(text=title.split(' - ')[1])
                except AttributeError:
                    log.debug('did not find %s listed' % title.split(' - ')[1])
                    continue
                try:
                    trailers_link = trailer.parent.next_sibling.next_sibling.contents[1].contents[0]
                except AttributeError:
                    log.debug('did not find trailer link tag')
                    continue
                try:
                    link = trailers_link['href'].replace('r640s', ''.join(['h', config.get('quality')]))
                except AttributeError:
                    log.debug('could not find download link')
                    continue
                entry = Entry(title, link)
                # Populate a couple entry fields for making pretty filenames
                entry['movie_name'], entry['apple_trailers_name'] = title.split(' - ')
                if genres:
                    entry['genres'] = ', '.join(list(genres))
                if release_year:
                    entry['movie_year'] = release_year
                if studio:
                    entry['movie_studio'] = studio
                result.append(entry)

        return result


@event('plugin.register')
def register_plugin():
    plugin.register(AppleTrailers, 'apple_trailers', api_ver=2)
