from pathlib import Path

from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.utils.log import log_once
from flexget.utils.template import RenderError

try:
    # NOTE: Importing other plugins is discouraged!
    from flexget.components.parsing import parsers as plugin_parsers
except ImportError:
    raise plugin.DependencyError(issued_by=__name__, missing='parsers')

logger = logger.bind(name='exists_series')


class FilterExistsSeries:
    """
    Intelligent series aware exists rejecting.

    Example::

      exists_series: /storage/series/
    """

    schema = {
        'anyOf': [
            one_or_more({'type': 'string', 'format': 'path'}),
            {
                'type': 'object',
                'properties': {
                    'path': one_or_more({'type': 'string', 'format': 'path'}),
                    'allow_different_qualities': {
                        'enum': ['better', True, False],
                        'default': False,
                    },
                },
                'required': ['path'],
                'additionalProperties': False,
            },
        ]
    }

    def prepare_config(self, config):
        # if config is not a dict, assign value to 'path' key
        if not isinstance(config, dict):
            config = {'path': config}
        # if only a single path is passed turn it into a 1 element list
        if isinstance(config['path'], str):
            config['path'] = [config['path']]
        return config

    @plugin.priority(-1)
    def on_task_filter(self, task, config):
        if not task.accepted:
            logger.debug('Scanning not needed')
            return
        config = self.prepare_config(config)
        accepted_series = {}
        paths = set()
        for entry in task.accepted:
            if 'series_parser' in entry:
                if entry['series_parser'].valid:
                    accepted_series.setdefault(entry['series_parser'].name, []).append(entry)
                    for folder in config['path']:
                        try:
                            paths.add(entry.render(folder))
                        except RenderError as e:
                            logger.error('Error rendering path `{}`: {}', folder, e)
                else:
                    logger.debug('entry {} series_parser invalid', entry['title'])
        if not accepted_series:
            logger.warning(
                'No accepted entries have series information. exists_series cannot filter them'
            )
            return

        # scan through
        # For speed, only test accepted entries since our priority should be after everything is accepted.
        for series in accepted_series:
            # make new parser from parser in entry
            series_parser = accepted_series[series][0]['series_parser']
            for folder in paths:
                folder = Path(folder).expanduser()
                if not folder.is_dir():
                    logger.warning('Directory {} does not exist', folder)
                    continue

                for filename in folder.iterdir():
                    # run parser on filename data
                    try:
                        disk_parser = plugin.get('parsing', self).parse_series(
                            data=filename.name, name=series_parser.name
                        )
                    except plugin_parsers.ParseWarning as pw:
                        disk_parser = pw.parsed
                        log_once(pw.value, logger=logger)
                    if disk_parser.valid:
                        logger.debug('name {} is same series as {}', filename.name, series)
                        logger.debug('disk_parser.identifier = {}', disk_parser.identifier)
                        logger.debug('disk_parser.quality = {}', disk_parser.quality)
                        logger.debug('disk_parser.proper_count = {}', disk_parser.proper_count)

                        for entry in accepted_series[series]:
                            logger.debug(
                                'series_parser.identifier = {}', entry['series_parser'].identifier
                            )
                            if disk_parser.identifier != entry['series_parser'].identifier:
                                logger.trace('wrong identifier')
                                continue
                            logger.debug(
                                'series_parser.quality = {}', entry['series_parser'].quality
                            )
                            if config.get('allow_different_qualities') == 'better':
                                if entry['series_parser'].quality > disk_parser.quality:
                                    logger.trace('better quality')
                                    continue
                            elif config.get('allow_different_qualities'):
                                if disk_parser.quality != entry['series_parser'].quality:
                                    logger.trace('wrong quality')
                                    continue
                            logger.debug(
                                'entry parser.proper_count = {}',
                                entry['series_parser'].proper_count,
                            )
                            if disk_parser.proper_count >= entry['series_parser'].proper_count:
                                entry.reject('episode already exists')
                                continue
                            else:
                                logger.trace('new one is better proper, allowing')
                                continue


@event('plugin.register')
def register_plugin():
    plugin.register(FilterExistsSeries, 'exists_series', interfaces=['task'], api_ver=2)
