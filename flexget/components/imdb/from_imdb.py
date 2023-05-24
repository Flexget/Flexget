from collections.abc import Iterable

from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached

logger = logger.bind(name='from_imdb')


class FromIMDB:
    """
    This plugin enables generating entries based on an entity, an entity being a person, character or company.
    It's based on IMDBpy which is required (pip install imdbpy). The basic config required just an IMDB ID of the
    required entity.

    For example:

        from_imdb: ch0001354

    Schema description:
    Other than ID, all other properties are meant to filter the full list that the entity generates.

    id: string that relates to a supported entity type. For example: 'nm0000375'. Required.
    job_types: a string or list with job types from job_types. Default is 'actor'.
    content_types: A string or list with content types from content_types. Default is 'movie'.
    max_entries: The maximum number of entries that can return. This value's purpose is basically flood protection
        against unruly configurations that will return too many results. Default is 200.

    Advanced config example:
        dynamic_movie_queue:
            from_imdb:
              id: co0051941
              job_types:
                - actor
                - director
              content_types: tv series
            accept_all: yes
            movie_queue: add

    """

    job_types = [
        'actor',
        'actress',
        'director',
        'producer',
        'writer',
        'self',
        'editor',
        'miscellaneous',
        'editorial department',
        'cinematographer',
        'visual effects',
        'thanks',
        'music department',
        'in development',
        'archive footage',
        'soundtrack',
    ]

    content_types = [
        'movie',
        'tv series',
        'tv mini series',
        'video game',
        'video movie',
        'tv movie',
        'episode',
    ]

    content_type_conversion = {
        'movie': 'movie',
        'tv series': 'tv',
        'tv mini series': 'tv',
        'tv movie': 'tv',
        'episode': 'tv',
        'video movie': 'video',
        'video game': 'video game',
    }

    character_content_type_conversion = {
        'movie': 'feature',
        'tv series': 'tv',
        'tv mini series': 'tv',
        'tv movie': 'tv',
        'episode': 'tv',
        'video movie': 'video',
        'video game': 'video-game',
    }

    jobs_without_content_type = ['actor', 'actress', 'self', 'in development', 'archive footage']

    imdb_pattern = one_or_more(
        {
            'type': 'string',
            'pattern': r'(nm|co|ch)\d{7,8}',
            'error_pattern': 'Get the id from the url of the person/company you want to use,'
            ' e.g. http://imdb.com/text/<id here>/blah',
        },
        unique_items=True,
    )

    schema = {
        'oneOf': [
            imdb_pattern,
            {
                'type': 'object',
                'properties': {
                    'id': imdb_pattern,
                    'job_types': one_or_more(
                        {'type': 'string', 'enum': job_types}, unique_items=True
                    ),
                    'content_types': one_or_more(
                        {'type': 'string', 'enum': content_types}, unique_items=True
                    ),
                    'max_entries': {'type': 'integer'},
                    'match_type': {'type': 'string', 'enum': ['strict', 'loose']},
                },
                'required': ['id'],
                'additionalProperties': False,
            },
        ]
    }

    def prepare_config(self, config):
        """
        Converts config to dict form and sets defaults if needed
        """
        config = config
        if isinstance(config, str):
            config = {'id': [config]}
        elif isinstance(config, list):
            config = {'id': config}
        if isinstance(config, dict) and not isinstance(config['id'], list):
            config['id'] = [config['id']]

        config.setdefault('content_types', [self.content_types[0]])
        config.setdefault('job_types', [self.job_types[0]])
        config.setdefault('max_entries', 200)
        config.setdefault('match_type', 'strict')

        if isinstance(config.get('content_types'), str):
            logger.debug('Converted content type from string to list.')
            config['content_types'] = [config['content_types']]

        if isinstance(config['job_types'], str):
            logger.debug('Converted job type from string to list.')
            config['job_types'] = [config['job_types']]
        # Special case in case user meant to add actress instead of actor (different job types in IMDB)
        if 'actor' in config['job_types'] and 'actress' not in config['job_types']:
            config['job_types'].append('actress')

        return config

    def get_items(self, config):
        items = []
        for id in config['id']:
            try:
                entity_type, entity_object = self.get_entity_type_and_object(id)
            except Exception as e:
                logger.error(
                    'Could not resolve entity via ID: {}. '
                    'Either error in config or unsupported entity. Error:{}',
                    id,
                    e,
                )
                continue
            items += self.get_items_by_entity(
                entity_type,
                entity_object,
                config.get('content_types'),
                config.get('job_types'),
                config.get('match_type'),
            )
        return set(items)

    def get_entity_type_and_object(self, imdb_id):
        """
        Return a tuple of entity type and entity object
        :param imdb_id: string which contains IMDB id
        :return: entity type, entity object (person, company, etc.)
        """
        if imdb_id.startswith('nm'):
            person = self.ia.get_person(imdb_id[2:])
            logger.info('Starting to retrieve items for person: {}', person)
            return 'Person', person
        elif imdb_id.startswith('co'):
            company = self.ia.get_company(imdb_id[2:])
            logger.info('Starting to retrieve items for company: {}', company)
            return 'Company', company
        elif imdb_id.startswith('ch'):
            character = self.ia.get_character(imdb_id[2:])
            logger.info('Starting to retrieve items for Character: {}', character)
            return 'Character', character

    def get_items_by_entity(
        self, entity_type, entity_object, content_types, job_types, match_type
    ):
        """
        Gets entity object and return movie list using relevant method
        """
        if entity_type == 'Company':
            return self.items_by_company(entity_object)

        if entity_type == 'Character':
            return self.items_by_character(entity_object, content_types, match_type)

        elif entity_type == 'Person':
            return self.items_by_person(entity_object, job_types, content_types, match_type)

    def flatten_list(self, _list):
        """
        Gets a list of lists and returns a flat list
        """
        for el in _list:
            if isinstance(el, Iterable) and not isinstance(el, str):
                yield from self.flatten_list(el)
            else:
                yield el

    def flat_list(self, non_flat_list, remove_none=False):
        flat_list = self.flatten_list(non_flat_list)
        if remove_none:
            flat_list = [_f for _f in flat_list if _f]
        return flat_list

    def filtered_items(self, unfiltered_items, content_types, match_type):
        items = []
        unfiltered_items = set(unfiltered_items)
        for item in sorted(unfiltered_items):
            if match_type == 'strict':
                logger.debug(
                    'Match type is strict, verifying item type to requested content types'
                )
                self.ia.update(item)
                if item['kind'] in content_types:
                    logger.verbose(
                        'Adding item "{}" to list. Item kind is "{}"', item, item['kind']
                    )
                    items.append(item)
                else:
                    logger.verbose('Rejecting item "{}". Item kind is "{}', item, item['kind'])
            else:
                logger.debug('Match type is loose, all items are being added')
                items.append(item)
        return items

    def items_by_person(self, person, job_types, content_types, match_type):
        """
        Return item list for a person object
        """
        unfiltered_items = self.flat_list(
            [self.items_by_job_type(person, job_type, content_types) for job_type in job_types],
            remove_none=True,
        )

        return self.filtered_items(unfiltered_items, content_types, match_type)

    def items_by_content_type(self, person, job_type, content_type):
        return [
            _f
            for _f in (person.get(job_type + ' ' + self.content_type_conversion[content_type], []))
            if _f
        ]

    def items_by_job_type(self, person, job_type, content_types):
        items = (
            person.get(job_type, [])
            if job_type in self.jobs_without_content_type
            else [
                person.get(job_type + ' ' + 'documentary', [])
                and person.get(job_type + ' ' + 'short', [])
                and self.items_by_content_type(person, job_type, content_type)
                if content_type == 'movie'
                else self.items_by_content_type(person, job_type, content_type)
                for content_type in content_types
            ]
        )
        return [_f for _f in items if _f]

    def items_by_character(self, character, content_types, match_type):
        """
        Return items list for a character object
        :param character: character object
        :param content_types: content types as defined in config
        :return:
        """
        unfiltered_items = self.flat_list(
            [
                character.get(self.character_content_type_conversion[content_type])
                for content_type in content_types
            ],
            remove_none=True,
        )

        return self.filtered_items(unfiltered_items, content_types, match_type)

    def items_by_company(self, company):
        """
        Return items list for a company object
        :param company: company object
        :return: company items list
        """
        return company.get('production companies')

    @cached('from_imdb', persist='2 hours')
    def on_task_input(self, task, config):
        try:
            from imdb import IMDb

            self.ia = IMDb()
        except ImportError:
            logger.error(
                'IMDBPY is required for this plugin. Please install using "pip install imdbpy"'
            )
            return

        entries = []
        config = self.prepare_config(config)
        items = self.get_items(config)
        if not items:
            logger.error('Could not get IMDB item list, check your configuration.')
            return
        for item in items:
            entry = Entry(
                title=item['title'],
                imdb_id='tt' + self.ia.get_imdbID(item),
                url='',
                imdb_url=self.ia.get_imdbURL(item),
            )

            if entry.isvalid():
                if entry not in entries:
                    entries.append(entry)
                    if entry and task.options.test:
                        logger.info("Test mode. Entry includes:")
                        for key, value in list(entry.items()):
                            logger.info('     {}: {}', key.capitalize(), value)
            else:
                logger.error('Invalid entry created? {}', entry)
        if len(entries) <= config.get('max_entries'):
            return entries
        else:
            logger.warning(
                'Number of entries ({}) exceeds maximum allowed value {}. '
                'Edit your filters or raise the maximum value by entering a higher "max_entries"',
                len(entries),
                config.get('max_entries'),
            )
            return


@event('plugin.register')
def register_plugin():
    plugin.register(FromIMDB, 'from_imdb', api_ver=2)
