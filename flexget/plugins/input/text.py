"""Plugin for text file or URL feeds via regex."""
import re
from pathlib import Path

from loguru import logger

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.cached_input import cached

logger = logger.bind(name='text')


class Text:
    """
    Parse any text for entries using regular expression.

    Example::

      url: <url>
      entry:
        <field>: <regexp to match value>
      format:
        <field>: <python string formatting>

    Note: each entry must have atleast two fields, title and url

    Example::

      text:
        url: http://www.nbc.com/Heroes/js/novels.js
        entry:
          title: novelTitle = "(.*)"
          url: novelPrint = "(.*)"
        format:
          url: http://www.nbc.com%(url)s
    """

    schema = {
        'type': 'object',
        'properties': {
            'url': {
                'oneOf': [
                    {'type': 'string', 'format': 'url'},
                    {'type': 'string', 'format': 'file'},
                ]
            },
            'encoding': {'type': 'string'},
            'entry': {
                'type': 'object',
                'properties': {
                    'url': {'type': 'string', 'format': 'regex'},
                    'title': {'type': 'string', 'format': 'regex'},
                },
                'additionalProperties': {'type': 'string', 'format': 'regex'},
                'required': ['url', 'title'],
            },
            'format': {'type': 'object', 'additionalProperties': {'type': 'string'}},
        },
        'required': ['entry', 'url'],
        'additonalProperties': False,
    }

    def format_entry(self, entry, d):
        for k, v in d.items():
            entry[k] = v % entry

    @cached('text')
    @plugin.internet(logger)
    def on_task_input(self, task, config):
        url = config['url']
        if '://' in url:
            lines = task.requests.get(url).text.split('\n')
        else:
            lines = Path(url).read_text(encoding=config.get('encoding', 'utf-8')).splitlines()

        entry_config = config.get('entry')
        format_config = config.get('format', {})

        entries = []
        # keep track what fields have been found
        used = {}
        entry = Entry()

        # now parse text
        for line in lines:
            for field, regexp in entry_config.items():
                # log.debug('search field: %s regexp: %s' % (field, regexp))
                match = re.search(regexp, line)
                if match:
                    # check if used field detected, in such case start with new entry
                    if field in used:
                        if entry.isvalid():
                            logger.info(
                                'Found field {} again before entry was completed. Adding current incomplete, but valid entry and moving to next.',
                                field,
                            )
                            self.format_entry(entry, format_config)
                            entries.append(entry)
                        else:
                            logger.info(
                                'Invalid data, entry field {} is already found once. Ignoring entry.',
                                field,
                            )
                        # start new entry
                        entry = Entry()
                        used = {}

                    # add field to entry
                    try:
                        entry[field] = match.group(1)
                    except IndexError:
                        logger.error('regex for field `{}` must contain a capture group', field)
                        raise plugin.PluginError(
                            'Your text plugin config contains errors, please correct them.'
                        )
                    used[field] = True
                    logger.debug('found field: {} value: {}', field, entry[field])

                # if all fields have been found
                if len(used) == len(entry_config):
                    # check that entry has atleast title and url
                    if not entry.isvalid():
                        logger.info(
                            'Invalid data, constructed entry is missing mandatory fields (title or url)'
                        )
                    else:
                        self.format_entry(entry, format_config)
                        entries.append(entry)
                        logger.debug('Added entry {}', entry)
                        # start new entry
                        entry = Entry()
                        used = {}
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(Text, 'text', api_ver=2)
