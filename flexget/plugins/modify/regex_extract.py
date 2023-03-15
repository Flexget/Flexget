import re

from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.utils.tools import ReList

logger = logger.bind(name='regex_extract')


class RegexExtract:
    r"""
    Updates an entry with the values of regex matched named groups

    Usage:

      regex_extract:
        field: <string>
        regex:
          - <regex>
        [prefix]: <string>


    Example:

      regex_extract:
        prefix: f1_
        field: title
        regex:
          - Formula\.?1.(?P<location>*?)

    """

    schema = {
        'type': 'object',
        'properties': {
            'prefix': {'type': 'string'},
            'field': {'type': 'string'},
            'regex': one_or_more({'type': 'string', 'format': 'regex'}),
        },
    }

    def on_task_start(self, task, config):
        regex = config.get('regex')
        if isinstance(regex, str):
            regex = [regex]
        self.regex_list = ReList(regex)

        # Check the regex
        try:
            for _ in self.regex_list:
                pass
        except re.error as e:
            raise plugin.PluginError('Error compiling regex: %s' % str(e))

    def on_task_modify(self, task, config):
        prefix = config.get('prefix')
        modified = 0

        for entry in task.entries:
            for rx in self.regex_list:
                entry_field = entry.get('title')
                logger.debug('Matching {} with regex: {}', entry_field, rx)
                try:
                    match = rx.match(entry_field)
                except re.error as e:
                    raise plugin.PluginError('Error encountered processing regex: %s' % str(e))
                if match:
                    logger.debug('Successfully matched {}', entry_field)
                    data = match.groupdict()
                    if prefix:
                        for key in list(data.keys()):
                            data[prefix + key] = data[key]
                            del data[key]
                    logger.debug('Values added to entry: {}', data)
                    entry.update(data)
                    modified += 1

        logger.info('{} entries matched and modified', modified)


@event('plugin.register')
def register_plugin():
    plugin.register(RegexExtract, 'regex_extract', api_ver=2)
