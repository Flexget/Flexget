from __future__ import unicode_literals, division, absolute_import

import logging
import re
from imdb._exceptions import IMDbDataAccessError
from flexget import plugin
from flexget.event import event
from flexget.entry import Entry


from imdb import IMDb
from flexget.config_schema import format_checker

log = logging.getLogger('smart_imdb')

ia = IMDb()

JOB_TYPES = ['actor', 'director', 'producer', 'writer', 'self',
             'editor', 'miscellaneous', 'editorial department', 'cinematographer',
             'visual effects', 'thanks', 'music department']
CONTENT_TYPES = ['movie', 'tv series', 'tv mini series', 'video game', 'video movie', 'tv movie', 'episode']
YEAR_FORMATS = [r'(\d{4)}$', r'\-(\d{4})$', r'(\d{4})\-$', r'(\d{4})\-(\d{4})$']
MIN_YEAR_RANGE = 1700
MAX_YEAR_RANGE = 3000


class SmartIMDB(object):

    entity_schema = {
        'type': 'object',
        'properties': {
            'name': {'type': 'string'},
            'id': {'type': 'string'},
            'jobtypes': {'type': 'array', 'items': {'type': 'string', 'enum': JOB_TYPES, 'default': 'actor'}},
            'content_types': {'type': 'array', 'items': {'type': 'string', 'enum': CONTENT_TYPES, 'default': 'movie'}}
        },
        'oneOf': [{'required': ['name']}, {'required': ['id']}],
        'error_oneOf': 'Either a name of ID are required.',
        'additionalProperties': False
    }

    schema = {
        'type': 'object',
        'properties': {
            'person': entity_schema,
            'genres': {"type": "array", "items": {"type": "string"}},
            'rating': {'type': 'number'},
            'votes': {'type': 'number'},
            'years': {'type': 'string'},
            'max_entries': {'type': 'number', 'default': 200},
            'strict_mode': {'type': 'boolean', 'default': False}
        },
        'required': ['person'],
        'additionalProperties': False

    }

    @staticmethod
    def is_imdb_id(string):
        """
        Checks if a given string matches IMDB id format
        :param string: Supposed IMDB ID
        :return: True if it matches
        """
        return re.search('[a-zA-Z]{2}(\d{7})', string)

    def get_all_movies_by_person(self, person):
        movies = []

        if person.get('id'):
            if self.is_imdb_id(person.get('id')):
                log.info('Detected IMDB ID %s, resolving person.' % person.get('id'))
                m = self.is_imdb_id(person.get('id'))
                IMDB_person = ia.get_person(m.group(1))
            if not person:
                log.warning('Could not resolve person from IMDB ID %s' % person.get('id'))
                return
        else:
            log.debug('Trying to search for person: %s' % person.get('name'))
            person_list = ia.search_person(person.get('name'))
            if person_list:
                IMDB_person = ia.get_person(person_list[0].personID)
            else:
                return

        if not person.get('jobtypes'):  # Special case, since 'actor' and 'actress' are separate keys in object
            log.debug('Getting movies for actor/actress: %s' % IMDB_person['name'])
            return IMDB_person.get('actor', IMDB_person.get('actress'))
        else:
            log.debug('Getting movies for %s with the following jobtypes: %s' %
                      (IMDB_person['name'], ' ,'.join(person.get('jobtypes'))))
            for jobtype in person['jobtypes']:
                for content_type in person.get('content_types'):
                    job_and_content = jobtype + ' ' + content_type
                    movies_by_jobtype = IMDB_person.get(job_and_content, IMDB_person.get(jobtype))
                    if movies_by_jobtype:
                        movies += movies_by_jobtype
            return movies

    def parse_year(self, year):
        """
        Receives 'year_range_format' string and parses it to return start and end dates
        :param year:
        :return: Tuple with start and end year. Uses max an min year values if either one is needed
        """
        if not year:
            return MIN_YEAR_RANGE, MAX_YEAR_RANGE

        for i in range(len(YEAR_FORMATS)):
            m = re.match(YEAR_FORMATS[i], year)
            if m:
                if i == 0:
                    return int(m.group(1)), int(m.group(1))
                elif i == 1:
                    return MIN_YEAR_RANGE, int(m.group(1))
                elif i == 2:
                    return int(m.group(1)), MAX_YEAR_RANGE
                elif i == 3:
                    return int(m.group(1)), int(m.group(2))
                else:
                    return MIN_YEAR_RANGE, MAX_YEAR_RANGE

    def on_task_input(self, task, config):
        entries = []
        person = config.get('person')

        if config.get('strict_mode'):
            default_rating = 0
            default_start_year = MIN_YEAR_RANGE
            default_end_year = MAX_YEAR_RANGE
            default_votes = 0
        else:
            default_rating = 10
            default_start_year = MAX_YEAR_RANGE
            default_end_year = MIN_YEAR_RANGE
            default_votes = 1000000

        movies = self.get_all_movies_by_person(person)

        if not movies:
            log.warning('Could not get movie list. Check your config:')
            return

        year_range = self.parse_year(config.get('years'))

        for movie in movies:
            try:
                ia.update(movie)
            except IMDbDataAccessError as e:
                log.error('An error has occurred, cannot get movie data: %s' % e)
                continue

            log.debug('Testing movie:' + movie.get('long imdb canonical title'))

            type_test = movie.get('kind') in person.get('content_types')
            rating_test = float(movie.get('rating', default_rating)) >= config.get('rating', 1)
            year_test = (movie.get('year', default_start_year)) >= year_range[0] and\
                        (movie.get('year', default_end_year)) <= year_range[1]
            votes_test = int(movie.get('votes', default_votes)) >= config.get('votes', 1)

            if type_test and rating_test and year_test and votes_test:
                entry = Entry(title=movie['title'],
                              imdb_id='tt' + ia.get_imdbID(movie),
                              url=ia.get_imdbURL(movie))
                if config.get('genres'):
                    for genre in config.get('genres'):
                        log.debug('Checking if %s is in movie genres: %s' %
                                  (genre, ' ,'.join(movie.get('genres', ''))))
                        if ' ,'.join(movie.get('genres', '')).lower().find(genre.lower()) != -1:
                            if entry.isvalid():
                                log.debug('Genres test passed')
                                if entry not in entries:
                                    entries.append(entry)
                                    if entry and task.options.test:
                                        log.info("Test mode. Entry includes:")
                                        log.info("    Title: %s" % entry["title"])
                                        log.info("    URL: %s" % entry["url"])
                                        log.info("    IMDB ID: %s" % entry["imdb_id"])
                            else:
                                log.error('Invalid entry created? %s' % entry)
                else:
                    log.debug('No genres requested in config, passing all genres.')
                    if entry.isvalid():
                        if entry not in entries:
                            entries.append(entry)
                            if entry and task.options.test:
                                log.info("Test mode. Entry includes:")
                                log.info("    Title: %s" % entry["title"])
                                log.info("    URL: %s" % entry["url"])
                                log.info("    IMDB ID: %s" % entry["imdb_id"])

                    else:
                        log.error('Invalid entry created? %s' % entry)

        if len(entries) <= config.get('max_entries'):
            return entries
        else:
            log.warning(
                'Number of entries (%s) exceeds maximum allowed value %s. '
                'Edit your filters or raise the maximum value by entering a higher "max_entries"' % (
                    len(entries), config.get('max_entries')))

            return


@event('plugin.register')
def register_plugin():
    plugin.register(SmartIMDB, 'smart_imdb', api_ver=2)
