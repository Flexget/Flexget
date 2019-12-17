from fnmatch import fnmatch

from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event

logger = logger.bind(name='content_filter')


class FilterContentFilter:
    """
    Rejects entries based on the filenames in the content. Torrent files only right now.

    Example::

      content_filter:
        require:
          - '*.avi'
          - '*.mkv'
    """

    schema = {
        'type': 'object',
        'properties': {
            # These two properties allow a string or list of strings
            'require': one_or_more({'type': 'string'}),
            'require_all': one_or_more({'type': 'string'}),
            'reject': one_or_more({'type': 'string'}),
            'require_mainfile': {'type': 'boolean', 'default': False},
            'strict': {'type': 'boolean', 'default': False},
        },
        'additionalProperties': False,
    }

    def prepare_config(self, config):
        for key in ['require', 'require_all', 'reject']:
            if key in config:
                if isinstance(config[key], str):
                    config[key] = [config[key]]
        return config

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

            def matching_mask(files, masks):
                """Returns matching mask if any files match any of the masks, false otherwise"""
                for file in files:
                    for mask in masks:
                        if fnmatch(file, mask):
                            return mask
                return False

            # Avoid confusion by printing a reject message to info log, as
            # download plugin has already printed a downloading message.
            if config.get('require'):
                if not matching_mask(files, config['require']):
                    logger.info(
                        'Entry {} does not have any of the required filetypes, rejecting',
                        entry['title'],
                    )
                    entry.reject('does not have any of the required filetypes', remember=True)
                    return True
            if config.get('require_all'):
                # Make sure each mask matches at least one of the contained files
                if not all(
                    any(fnmatch(file, mask) for file in files) for mask in config['require_all']
                ):
                    logger.info(
                        'Entry {} does not have all of the required filetypes, rejecting',
                        entry['title'],
                    )
                    entry.reject('does not have all of the required filetypes', remember=True)
                    return True
            if config.get('reject'):
                mask = matching_mask(files, config['reject'])
                if mask:
                    logger.info('Entry {} has banned file {}, rejecting', entry['title'], mask)
                    entry.reject('has banned file %s' % mask, remember=True)
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

    @plugin.priority(150)
    def on_task_modify(self, task, config):
        if task.options.test or task.options.learn:
            logger.info(
                'Plugin is partially disabled with --test and --learn '
                'because content filename information may not be available'
            )
            # return

        config = self.prepare_config(config)
        for entry in task.accepted:
            if self.process_entry(task, entry, config):
                task.rerun(plugin='content_filter')
            elif 'content_files' not in entry and config.get('strict'):
                entry.reject('no content files parsed for entry', remember=True)
                task.rerun(plugin='content_filter')


@event('plugin.register')
def register_plugin():
    plugin.register(FilterContentFilter, 'content_filter', api_ver=2)
