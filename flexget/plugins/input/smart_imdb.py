from __future__ import unicode_literals, division, absolute_import

import logging
import re
from jsonschema.compat import str_types
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

YEAR_FORMATS = [r'^((19|20)\d{2})$', r'^\-((19|20)\d{2})$', r'^((19|20)\d{2})\-$', r'^((19|20)\d{2})\-((19|20)\d{2}$)']

ENTITIES_FORMATS = {
    'Person': r'nm(\d{7})',
    'Company': r'co(\d{7})',
    'Character': r'ch(\d{7})'
}

MIN_YEAR_RANGE = 1900
MAX_YEAR_RANGE = 2099


class SmartIMDB(object):
    """
    This plugin enables generating entries based on an entity, an entity being a person, character or company.
    It's based on IMDBpy which is required (pip install imdbpy). The basic config required just an IMDB ID of the
    required entity.

    For example:

        smart_imdb: 'http://www.imdb.com/character/ch0001354/?ref_=tt_cl_t1'

    ID format is not important as relevant ID is captured via regex.

    Schema description:
    Other than ID, all other properties are meant to filter the full list that the entity generates.

    id: string that relates to a supported entity type. For example: 'nm0000375'. Required.
    job_types: a string or list with job types from JOB_TYPES. Default is 'actor'.
    content_types: A string or list with content types from CONTENT_TYPES. Default is 'movie'.
    include_genres: A string or list with genres to include when matching a movie. Can also contain match_type,
        which decided on the filter type.
        If match_type is 'any', if ANY of the included genres are listed in the filtered movie, it will pass the filter.
        If match_type is 'all, if ALL of the included genres are listed in the filtered movie, it will pass the filter.
        If match_type is 'exact, if EXACTLY all of the included genres are listed in the filtered movie,
        it will pass the filter. Default match_type is 'any'.
    exclude_genres: Exactly like include_genres but relates to which genres the item should not hold.
    rating: A number between 0 and 10 that will be matched against the rating of the movie. If movie rating is higher
        or equal, it will pass the filter.
    votes: A number that will be matched against the votes of the movie. If movie number of votes is higher
        or equal, it will pass the filter.
    years: A string that determines which years to filter. For example:
        2004: If movie year is 2004, it will pass filter.
        2004-: If movie year is 2004 and higher, it will pass filter.
        -2004: If movie year is before 2004, it will pass filter.
        2000-2004: If movie year is between 2000 and 2004, it will pass filter.
    max_entries: The maximum number of entries that can return. This value's purpose is basically flood protection
        against unruly configurations that will return too many results. Default is 200.
    strict_mode: A boolean value that determines what to do in case an item does not have year, rating or votes listed
        and the configuration holds any of those. If set to 'True', it will cause an item that does not hold one of
        these properties to fail the filter. Default is 'False'.

    Advanced config example:
        smart_movie_queue:
            smart_imdb:
              id: 'http://www.imdb.com/company/co0051941/?ref_=fn_al_co_2'
              job_types:
                - actor
                - director
              content_types:
                - tv series
              rating: 5.6
              include_genres:
                genres:
                  - action
                  - comedy
                match_type: any
              exclude_genres: animation
              years: '2005-'
              strict_mode: yes
            accept_all: yes
            movie_queue: add

    """
    genres_schema = {
        'oneOf': [
            {'type': 'object',
             'properties': {
                 'genres': {"type": "array", "items": {"type": "string"}},
                 'match_type': {'type': 'string', 'enum': ['any', 'all', 'exact']}
             },
             'required': ['genres'],
             'additionalProperties': False
             },
            {'type': 'string'}
        ]
    }

    job_types = {'type': 'string', 'enum': JOB_TYPES}
    content_types = {'type': 'string', 'enum': CONTENT_TYPES}

    schema = {
        'oneOf': [
            {'type': 'string'},
            {'type': 'object',
             'properties': {
                 'id': {'type': 'string'},
                 'job_types': {
                     'oneOf': [
                         {'type': 'array', 'items': job_types},
                         job_types
                     ]
                 },
                 'content_types': {
                     'oneOf': [
                         {'type': 'array', 'items': content_types},
                         content_types
                     ]
                 },
                 'include_genres': genres_schema,
                 'exclude_genres': genres_schema,
                 'rating': {'type': 'number', 'minimum': 0, 'maximum': 10},
                 'votes': {'type': 'number'},
                 'years': {'type': ['string', 'number'], 'format': 'year_format'},
                 'actor_position': {'type': 'number', 'minimum': 1},
                 'max_entries': {'type': 'number'},
                 'strict_mode': {'type': 'boolean'}
             },
             'required': ['id'],
             'additionalProperties': False
             }
        ]
    }

    def entity_type_and_object(self, imdb_id):
        """
        Return a tuple of entity type and entity object
        :param imdb_id: string which contains IMDB id
        :return: entity type, entity object (person, company, etc.)
        """
        for imdb_entity_type, imdb_entity_format in ENTITIES_FORMATS.items():
            m = re.search(imdb_entity_format, imdb_id)
            if m:
                if imdb_entity_type == 'Person':
                    log.info('Starting to retrieve items for person: %s' % ia.get_person(m.group(1)))
                    return imdb_entity_type, ia.get_person(m.group(1))
                elif imdb_entity_type == 'Company':
                    log.info('Starting to retrieve items for company: %s' % ia.get_company(m.group(1)))
                    return imdb_entity_type, ia.get_company(m.group(1))
                elif imdb_entity_type == 'Character':
                    log.info('Starting to retrieve items for Character: %s' % ia.get_character(m.group(1)))
                    return imdb_entity_type, ia.get_character(m.group(1))

    def items_by_entity(self, entity_type, entity_object, content_types, job_types):
        """
        Gets entity object and return movie list
        :param entity_type: Person, company, etc.
        :param entity_object: The object itself
        :param content_types: as defined in config
        :param job_types: As defined in config
        :return:
        """
        movies = []

        if entity_type == 'Company':
            return entity_object.get('production companies')

        if entity_type == 'Character':
            return entity_object.get('feature', []) + entity_object.get('tv', []) \
                   + entity_object.get('video-game', []) + entity_object.get('video', [])

        elif entity_type == 'Person':
            if 'actor' in job_types:
                job_types.append('actress')  # Special case: Actress are listed differently than actor
            for job_type in job_types:
                for content_type in content_types:
                    job_and_content = job_type + ' ' + content_type
                    log.debug('Searching for movies that correlates to: ' + job_and_content)
                    movies_by_job_type = entity_object.get(job_and_content, entity_object.get(job_type))
                    if movies_by_job_type:
                        for movie in movies_by_job_type:
                            if movie not in movies:
                                log.verbose('Found item: ' + movie.get('title') + ', adding to unfiltered list')
                                movies.append(movie)
                            else:
                                log.debug('Movie ' + str(movie) + ' already found in list, skipping.')
            return movies

    def parse_year(self, year):
        """
        Receives 'year_range_format' string and parses it to return start and end dates
        :param year:
        :return: Tuple with start and end year. Uses max an min year values if either one is needed
        """
        if not year:
            log.debug('No year filter in config, returning defaults.')
            return MIN_YEAR_RANGE, MAX_YEAR_RANGE

        for i in range(len(YEAR_FORMATS)):
            m = re.match(YEAR_FORMATS[i], year)
            if m:
                if i == 0:
                    log.debug('Matched year regex group ' + str(i))
                    return int(m.group(1)), int(m.group(1))
                elif i == 1:
                    log.debug('Matched year regex group ' + str(i))
                    return MIN_YEAR_RANGE, int(m.group(1))
                elif i == 2:
                    log.debug('Matched year regex group ' + str(i))
                    return int(m.group(1)), MAX_YEAR_RANGE
                elif i == 3:
                    log.debug('Matched year regex group ' + str(i))
                    return int(m.group(1)), int(m.group(3))

        return MIN_YEAR_RANGE, MAX_YEAR_RANGE

    def clean_list(self, genres_list):
        """
        Gets a list and return a new list with lowercase elements
        :param genres_list: List of genres to clean
        :return:
        """
        if not isinstance(genres_list, list):
            return

        new_list = []
        for item in genres_list:
            new_list.append(str(item).lower())
        return new_list

    def genres_match(self, user_genres, movie_genres):
        """
        Takes a genres object from config schema and tries to match it with movie genres according to match type.
        If match type is 'any', will return true if any of the user specified genres exists in the movie genres list.
        if match type is 'all' will return true if all of the user specified genres exists in the movie genres list.
        if match type is 'exact' will return true if exactly all of the user specified genres exists in the movie genres
        list.
        :param user_genres: Genres from config
        :param movie_genres: Movie genres
        :return:
        """
        if not bool(user_genres):
            return True

        user_genres_list = self.clean_list(user_genres.get('genres'))
        movie_genres_list = self.clean_list(movie_genres)
        match_type = user_genres.get('match_type')
        log.debug('Matching user genres: ' + ', '.join(user_genres_list) + ' with movie genres: ' +
                  ', '.join(movie_genres_list) + ' and match type: ' + match_type)

        if match_type == 'any':
            return bool(
                set(user_genres_list) & set(movie_genres_list))
        elif match_type == 'all':
            return not bool(
                set(user_genres_list) - set(movie_genres_list))
        elif match_type == 'exact':
            return not bool(
                set(user_genres_list) ^ set(movie_genres_list))

    @format_checker.checks('year_format', raises=ValueError)
    def is_year_format(instance):
        if not isinstance(instance, str_types):
            return True

        for regex in YEAR_FORMATS:
            m = re.match(regex, instance)
            if m:
                return True
        raise ValueError('Invalid year format, or years out of range of %d to %d. Please check config.'
                         % (MIN_YEAR_RANGE, MAX_YEAR_RANGE))

    def prepare_config(self, config):
        """
        Converts config to dict form and sets defaults if needed
        """
        if not isinstance(config, dict):
            config = {'id': config}

        config.setdefault('content_types', [CONTENT_TYPES[0]])
        config.setdefault('job_types', [JOB_TYPES[0]])
        config.setdefault('max_entries', 200)
        config.setdefault('strict_mode', False)

        if isinstance(config.get('content_types'), str_types):
            log.debug('Converted content type from string to list.')
            config['content_types'] = [config['content_types']]

        if isinstance(config['job_types'], str_types):
            log.debug('Converted job type from string to list.')
            config['job_types'] = [config['job_types']]

        if config.get('include_genres'):
            if isinstance(config.get('include_genres'), str_types):
                config['include_genres'] = {'genres': [config.get('include_genres')]}
            config['include_genres'].setdefault('match_type', 'any')

        if config.get('exclude_genres'):
            if isinstance(config.get('exclude_genres'), str_types):
                config['exclude_genres'] = {'genres': [config.get('exclude_genres')]}
            config['exclude_genres'].setdefault('match_type', 'any')

        if config.get('years'):
            config['years'] = str(config.get('years'))

        return config

    def on_task_input(self, task, config):
        entries = []

        config = self.prepare_config(config)

        include_list = config.get('include_genres')
        exclude_list = config.get('exclude_genres')

        try:
            entity_type, entity_object = self.entity_type_and_object(config.get('id'))
        except Exception as e:
            log.error('Could not resolve entity via ID. Either error in config or unsupported entity: %s' % e)
            return

        items = self.items_by_entity(entity_type, entity_object,
                                     config.get('content_types'), config.get('job_types'))

        if not items:
            log.error('Could not get IMDB item list, check your configuration.')
            return

        year_range = self.parse_year(config.get('years'))
        log.info('Retrieved %d items, starting to filter list.' % len(items))

        for item in items:
            try:
                ia.update(item)
            except Exception as e:
                log.error('An error has occurred, cannot get item data: %s' % e)
                continue

            log.verbose(
                'Testing if item: ' + item.get('long imdb canonical title') + ' qualifies for adding to entries.')

            type_test = item.get('kind') in config.get('content_types')
            log.verbose('Item kind: ' + item.get('kind') + ' found in config types ' +
                        ', '.join(config.get('content_types')) + ': ' + str(type_test))

            if config.get('rating'):
                if not item.get('rating'):
                    if config.get('strict_mode'):
                        log.verbose('Strict mode: Item does not have rating value, skipping movie.')
                        rating_test = False
                    else:
                        log.verbose('Item does not have rating listed, skipping test.')
                        rating_test = True
                else:
                    rating_test = float(item.get('rating')) >= config.get('rating', 1)
                    log.verbose('Item rating: ' + str(item.get('rating')) +
                                ' is higher or equal to: ' + str(config.get('rating', '1')) + ': ' + str(rating_test))
            else:
                log.verbose('No rating test required, skipping rating test.')
                rating_test = True

            if config.get('years'):
                if not item.get('year'):
                    if config.get('strict_mode'):
                        log.verbose('Strict mode: Item does not have year value, skipping movie.')
                        year_test = False
                    else:
                        log.verbose('Item does not have year listed, skipping test.')
                        year_test = True
                else:
                    year_test = (item.get('year') >= year_range[0] and (item.get('year') <= year_range[1]))
                    log.verbose(u'Item year: {0} is in given range of {1} and {2}: {3}'.format(str((item.get('year'))),
                                                                                               str(year_range[0]),
                                                                                               str(year_range[1]),
                                                                                               str(year_test)))
            else:
                log.verbose('No years test required, skipping year test.')
                year_test = True

            if config.get('votes'):
                if not item.get('votes'):
                    if config.get('strict_mode'):
                        log.verbose('Strict mode: Item does not have votes value, skipping movie.')
                        votes_test = False
                    else:
                        log.verbose('Item does not have votes listed, skipping test.')
                        votes_test = True
                else:
                    votes_test = int(item.get('votes')) >= config.get('votes', 1)
                    log.verbose('Item votes: ' + str(item.get('votes')) +
                                ' are higher or equal to: ' + str(config.get('votes', '1')) + ': ' + str(votes_test))
            else:
                log.verbose('No votes test required, skipping votes test.')
                votes_test = True

            if exclude_list:
                exclude_test = not self.genres_match(exclude_list, item.get('genres', []))
                log.verbose('Exclude genres: ' + ', '.join(exclude_list.get('genres', [])) + ' with match type ' +
                            exclude_list.get('match_type') + ' are not found in item genres: ' +
                            ', '.join(item.get('genres', [])) + ': ' + str(exclude_test))
            else:
                log.verbose('No genres exclude test required, skipping exclude list test.')
                exclude_test = True

            if include_list:
                include_test = self.genres_match(include_list, item.get('genres', []))
                log.verbose('Include genres: ' + ', '.join(include_list.get('genres', [])) +
                            ' with match type ' + include_list.get('match_type') + ' are found in item genres: ' +
                            ', '.join(item.get('genres', [])) + ': ' + str(include_test))
            else:
                log.verbose('No genres include test required, skipping include list test.')
                include_test = True

            if config.get('actor_position'):
                if entity_type != 'Person':
                    log.verbose('Actor position value detected but entity type is not person. Skipping test.')
                    position_test = True
                else:
                    if 'actor' not in config.get('job_types'):
                        log.verbose('Actor position value detected but job type "actor" is not in list. Skipping test.')
                        position_test = True
                    else:
                        actor_position = 0
                        found = False
                        while not found and actor_position < len(item.get('cast', [])):
                            if item['cast'][actor_position].get('name') == entity_object.get('name'):
                                found = True
                            actor_position += 1
                        position_test = actor_position <= config.get('actor_position')
                        log.verbose('Position test: Actor %s position in cast is %d and it higher or equal to %d. %s' %
                                    (entity_object.get('name'), actor_position, config.get('actor_position'),
                                     str(position_test)))
            else:
                log.verbose('No position test required, passing test.')
                position_test = True

            if type_test and rating_test and year_test and votes_test and exclude_test and include_test and \
                    position_test:
                entry = Entry(title=item['title'],
                              imdb_id='tt' + ia.get_imdbID(item),
                              url='')
                if entry.isvalid():
                    if entry not in entries:
                        entries.append(entry)
                        if entry and task.options.test:
                            log.info("Test mode. Entry includes:")
                            log.info("    Title: %s" % entry["title"])
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
