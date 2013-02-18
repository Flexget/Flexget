from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.plugin import register_plugin, register_parser_option

log = logging.getLogger('cli_config')


class CliConfig(object):

    """
    Allows specifying yml configuration values from commandline parameters.

    Yml variables are prefixed with dollar sign ($).
    Commandline parameter must be comma separated list of variable=values.

    Configuration example::

      tasks:
        my task:
          rss: $url
          download: $path

    Commandline example::

      --cli-config "url=http://some.url/, path=~/downloads"

    """

    def __init__(self):
        self.replaces = {}

    def replace_item(self, item):
        if isinstance(item, basestring):
            # Do replacement in text objects
            for key, val in self.replaces.iteritems():
                item = item.replace('$%s' % key, val)
            return item
        elif isinstance(item, list):
            # Make a new list with replacements done on each item
            return map(self.replace_item, item)
        elif isinstance(item, dict):
            # Make a new dict with replacements done on keys and values
            return dict(map(self.replace_item, kv_pair) for kv_pair in item.iteritems())
        else:
            # We don't know how to do replacements on this item, just return it
            return item

    def parse_replaces(self, task):
        """Parses commandline string into internal dict"""
        arg = task.manager.options.cli_config
        if not arg:
            return False  # nothing to process
        if self.replaces:
            return True  # already parsed
        for item in arg.split(','):
            try:
                key, value = item.split('=', 1)
            except ValueError:
                log.critical('Invalid --cli-config, no name for %s' % item)
                continue
            self.replaces[key.strip()] = value.strip()
        return True

    def on_process_start(self, task):
        if self.parse_replaces(task):
            task.config = self.replace_item(task.config)
            log.debug(task.config)

register_plugin(CliConfig, 'cli_config', builtin=True)
register_parser_option('--cli-config', action='store', dest='cli_config', default=False,
                       metavar='PARAMS', help='Configuration parameters trough commandline.')
