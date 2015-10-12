from __future__ import unicode_literals, division, absolute_import

import logging
from jsonschema.compat import str_types
from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.entry import Entry

from flexget.utils.cached_input import cached

log = logging.getLogger('dynamic_imdb')

JOB_TYPES = ['actor', 'actress', 'director', 'producer', 'writer', 'self',
             'editor', 'miscellaneous', 'editorial department', 'cinematographer',
             'visual effects', 'thanks', 'music department', 'in development', 'archive footage', 'soundtrack']

CONTENT_TYPES = ['movie', 'tv series', 'tv mini series', 'video game', 'video movie', 'tv movie', 'episode']

CONTENT_TYPE_CONVERSION = {
    'movie': 'movie',
    'tv series': 'tv',
    'tv mini series': 'tv',
    'tv movie': 'tv',
    'episode': 'tv',
    'video movie': 'video',
    'video game': 'video game'
}

CHARACTER_CONTENT_TYPE_CONVERSION = {
    'movie': 'feature',
    'tv series': 'tv',
    'tv mini series': 'tv',
    'tv movie': 'tv',
    'episode': 'tv',
    'video movie': 'video',
    'video game': 'video-game',
}

JOBS_WITHOUT_CONTENT_TYPE = ['actor', 'actress', 'self', 'in development', 'archive footage']


class DynamicIMDB(object):
    """
    This plugin enables generating entries based on an entity, an entity being a person, character or company.
    It's based on IMDBpy which is required (pip install imdbpy). The basic config required just an IMDB ID of the
    required entity.

    For example:

        dynamic_imdb: ch0001354

    Schema description:
    Other than ID, all other properties are meant to filter the full list that the entity generates.

    id: string that relates to a supported entity type. For example: 'nm0000375'. Required.
    job_types: a string or list with job types from JOB_TYPES. Default is 'actor'.
    content_types: A string or list with content types from CONTENT_TYPES. Default is 'movie'.
    max_entries: The maximum number of entries that can return. This value's purpose is basically flood protection
        against unruly configurations that will return too many results. Default is 200.

    Advanced config example:
        dynamic_movie_queue:
            dynamic_imdb:
              id: co0051941
              job_types:
                - actor
                - director
              content_types: tv series
            accept_all: yes
            movie_queue: add

    """
    imdb_pattern = {'type': 'string',
                    'pattern': r'(nm|co|ch)\d{7}',
                    'error_pattern': 'Get the id from the url of the person/company you want to use,'
                                     ' e.g. http://imdb.com/person/<id here>/blah'}

    schema = {
        'oneOf': [
            imdb_pattern,
            {'type': 'object',
             'properties': {
                 'id': imdb_pattern,
                 'job_types': one_or_more({'type': 'string', 'enum': JOB_TYPES}),
                 'content_types': one_or_more({'type': 'string', 'enum': CONTENT_TYPES}),
                 'max_entries': {'type': 'integer'}
             },
             'required': ['id'],
             'additionalProperties': False
             }
        ],

    }

    def get_entity_type_and_object(self, imdb_id):
        """
        Return a tuple of entity type and entity object
        :param imdb_id: string which contains IMDB id
        :return: entity type, entity object (person, company, etc.)
        """
        if imdb_id.startswith('nm'):
            person = self.ia.get_person(imdb_id[2:])
            log.info('Starting to retrieve items for person: %s' % person)
            return 'Person', person
        elif imdb_id.startswith('co'):
            company = self.ia.get_company(imdb_id[2:])
            log.info('Starting to retrieve items for company: %s' % company)
            return 'Company', company
        elif imdb_id.startswith('ch'):
            character = self.ia.get_character(imdb_id[2:])
            log.info('Starting to retrieve items for Character: %s' % character)
            return 'Character', character

    def get_items_by_person(self, person, job_types, content_types):
        """
        Return item list for a person object
        :param person: Person object
        :param job_types: Relevant job types as inputted in config
        :param content_types: Relevant content types as inputted in config
        :return: Person item list
        """
        items = []
        for job_type in job_types:
            if job_type in JOBS_WITHOUT_CONTENT_TYPE:
                log.debug('Searching for movies that correlates to: ' + job_type)
                items += person.get(job_type)
                continue
            else:
                for content_type in content_types:
                    job_and_content = job_type + ' ' + CONTENT_TYPE_CONVERSION[content_type]
                    log.debug('Searching for movies that correlates to: ' + job_and_content)
                    movies_by_job_type = person.get(job_and_content)
                    if content_type == 'movie':
                        log.debug('Searching for short movies and documentaries.')
                        movies_by_job_type += person.get(job_type + ' ' + 'documentary', [])
                        movies_by_job_type += person.get(job_type + ' ' + 'short', [])
                    if movies_by_job_type:
                        for item in movies_by_job_type:
                            self.ia.update(item)
                            if item not in items and item['kind'] in content_types:
                                log.debug('Found item: ' + item.get('title') + ', adding to unfiltered list')
                                items.append(item)
                            else:
                                log.debug('Item ' + str(item) + ' already found in list, skipping.')
        return items

    def get_items_by_character(self, character, content_types):
        """
        Return items list for a character object
        :param character: character object
        :param content_types: content types as defined in config
        :return:
        """
        items = []
        for content_type in content_types:
            items += character.get(CHARACTER_CONTENT_TYPE_CONVERSION[content_type], [])
        return items

    def get_items_by_company(self, company):
        """
        Return items list for a company object
        :param company: company object
        :return: company items list
        """
        return company.get('production companies')

    def get_items_by_entity(self, entity_type, entity_object, content_types, job_types):
        """
        Gets entity object and return movie list using relevant method
        :param entity_type: Person, company, etc.
        :param entity_object: The object itself
        :param content_types: content types as defined in config
        :param job_types: job types s defined in config
        :return:
        """
        if entity_type == 'Company':
            return self.get_items_by_company(entity_object)

        if entity_type == 'Character':
            return self.get_items_by_character(entity_object, content_types)

        elif entity_type == 'Person':
            return self.get_items_by_person(entity_object, job_types, content_types)

    def prepare_config(self, config):
        """
        Converts config to dict form and sets defaults if needed
        """
        if not isinstance(config, dict):
            config = {'id': config}

        config.setdefault('content_types', [CONTENT_TYPES[0]])
        config.setdefault('job_types', [JOB_TYPES[0]])
        config.setdefault('max_entries', 200)

        if isinstance(config.get('content_types'), str_types):
            log.debug('Converted content type from string to list.')
            config['content_types'] = [config['content_types']]

        if isinstance(config['job_types'], str_types):
            log.debug('Converted job type from string to list.')
            config['job_types'] = [config['job_types']]

        return config

    @cached('dynamic_imdb', persist='2 hours')
    def on_task_input(self, task, config):
        try:
            from imdb import IMDb
        except ImportError:
            log.error('IMDBPY is requires for this plugin. Please install using "pip install imdbpy"')
            return

        self.ia = IMDb()
        entries = []

        config = self.prepare_config(config)

        try:
            entity_type, entity_object = self.get_entity_type_and_object(config.get('id'))
        except Exception as e:
            log.error('Could not resolve entity via ID. Either error in config or unsupported entity: %s' % e)
            return

        items = self.get_items_by_entity(entity_type, entity_object,
                                     config.get('content_types'), config.get('job_types'))

        if not items:
            log.error('Could not get IMDB item list, check your configuration.')
            return

        log.info('Retrieved %d items.' % len(items))

        for item in items:
            entry = Entry(title=item['title'],
                          imdb_id='tt' + self.ia.get_imdbID(item),
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
    plugin.register(DynamicIMDB, 'dynamic_imdb', api_ver=2)
