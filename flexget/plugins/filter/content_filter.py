import re
from fnmatch import fnmatch

from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.utils.tools import aggregate_inputs

logger = logger.bind(name='content_filter')


class FilterContentFilter:
    """
    Rejects entries based on the filenames in the content. Torrent files only right now.

    Example::

      content_filter:
        require:
          - '*.avi'
          - '*.mkv'
        reject:
          from:
            - regexp_list: my-rejections
    """

    lists_schema = {
        'oneOf': [
            {'type': 'string'},
            {
                'type': 'array',
                'items': {'type': 'string'},
                'minItems': 1,
                'uniqueItems': False,
            },
            {
                'type': 'object',
                'properties': {
                    'from': {
                        'type': 'array',
                        'items': {
                            'allOf': [
                                {'$ref': '/schema/plugins?phase=input'},
                                {
                                    'maxProperties': 1,
                                    'error_maxProperties': 'Plugin options within content_filter plugin must be indented '
                                    '2 more spaces than the first letter of the plugin name.',
                                    'minProperties': 1,
                                },
                            ]
                        },
                    }
                },
            },
        ]
    }

    schema = {
        'type': 'object',
        'properties': {
            'min_files': {'type': 'integer'},
            'max_files': {'type': 'integer'},
            # These two properties allow a string or list of strings
            'require': lists_schema,
            'require_all': lists_schema,
            'reject': lists_schema,
            'require_mainfile': {'type': 'boolean', 'default': False},
            'strict': {'type': 'boolean', 'default': False},
            'regexp_mode': {'type': 'boolean', 'default': False},
        },
        'additionalProperties': False,
    }

    def process_entry(self, task, entry, config):
        """
        Process an entry and reject it if it doesn't pass filter.

        :param task: Task entry belongs to.
        :param entry: Entry to process
        :return: True, if entry was rejected.
        """
        if 'content_files' in entry:
            files = entry['content_files']
            logger.debug('{} files: {}', entry['title'], files)

            def matching_mask(file, mask):
                """Returns matching mask if any files match any of the masks, false otherwise"""
                if config.get('regexp_mode'):
                    return re.search(mask, file, re.IGNORECASE)
                return fnmatch(file, mask)

            # Avoid confusion by printing a reject message to info log, as
            # download plugin has already printed a downloading message.
            if config.get('require') and not any(
                any(matching_mask(file, mask) for file in files) for mask in config['require']
            ):
                logger.info(
                    'Entry {} does not have any of the required files, rejecting',
                    entry['title'],
                )
                entry.reject('does not have any of the required files', remember=True)
                return True
            # Make sure each mask matches at least one of the contained files
            if config.get('require_all') and not all(
                any(matching_mask(file, mask) for file in files) for mask in config['require_all']
            ):
                logger.info(
                    'Entry {} does not have all of the required files, rejecting',
                    entry['title'],
                )
                entry.reject('does not have all of the required files', remember=True)
                return True
            if config.get('reject'):
                for mask in config['reject']:
                    if any(matching_mask(file, mask) for file in files):
                        logger.info('Entry {} has banned file {}, rejecting', entry['title'], mask)
                        entry.reject(f'has banned file {mask}', remember=True)
                        return True
            if config.get('require_mainfile') and len(files) > 1:
                best = None
                for f in entry['torrent'].get_filelist():
                    if not best or f['size'] > best:
                        best = f['size']
                if (100 * float(best) / float(entry['torrent'].size)) < 90:
                    logger.info('Entry {} does not have a main file, rejecting', entry['title'])
                    entry.reject('does not have a main file', remember=True)
                    return True
            if config.get('min_files') and len(files) < config['min_files']:
                logger.info(
                    f'Entry {entry["title"]} has {len(files)} files. Minimum is {config["min_files"]}. Rejecting.'
                )
                entry.reject(f'Has less than {config["min_files"]} files', remember=True)
                return True
            if config.get('max_files') and len(files) > config['max_files']:
                logger.info(
                    f'Entry {entry["title"]} has {len(files)} files. Maximum is {config["max_files"]}. Rejecting.'
                )
                entry.reject(f'Has more than {config["max_files"]} files', remember=True)
                return True
            return None
        return None

    @plugin.priority(150)
    def on_task_modify(self, task, config):
        if task.options.test or task.options.learn:
            logger.info(
                'Plugin is partially disabled with --test and --learn '
                'because content filename information may not be available'
            )
            # return

        for key in ['require', 'require_all', 'reject']:
            if key in config:
                if isinstance(config[key], str):
                    config[key] = [config[key]]
                elif isinstance(config[key], dict) and config[key].get('from'):
                    config[key] = [
                        entry['title'] for entry in aggregate_inputs(task, config[key]['from'])
                    ]

        for entry in task.accepted:
            if self.process_entry(task, entry, config):
                task.rerun(plugin='content_filter')
            elif 'content_files' not in entry and config.get('strict'):
                entry.reject('no content files parsed for entry', remember=True)
                task.rerun(plugin='content_filter')


@event('plugin.register')
def register_plugin():
    plugin.register(FilterContentFilter, 'content_filter', api_ver=2)
