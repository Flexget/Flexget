import logging
from flexget.plugin import register_plugin, register_parser_option

log = logging.getLogger('cli_config')


class CliConfig(object):

    """
        Allows specifying yml configuration values from commandline parameters.

        Yml variables are prefixed with dollar sign ($).
        Commandline parameter must be comma separated list of variable=values.

        Configuration example:

        feeds:
          my feed:
            rss: $url
            download: $path

        Commandline example:

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
            # Make a new list with replacements done
            return [self.replace_item(x) for x in item]
        elif isinstance(item, dict):
            # Make a new dict with replacements done for keys and values
            return dict((self.replace_item(key), self.replace_item(val)) for key, val in item.iteritems())
        else:
            # We don't know how to do replacements on this item, just return it
            return item

    def parse_replaces(self, feed):
        """Parses commandline string into internal dict"""
        s = feed.manager.options.cli_config
        if not s:
            return False # nothing to process
        if self.replaces:
            return True # already parsed
        items = s.split(',')
        for item in items:
            try:
                key = item[:item.index('=')]
            except ValueError:
                log.critical('Invalid --cli-config, no name for %s' % item)
                continue
            value = item[item.index('=') + 1:]
            self.replaces[key.strip()] = value.strip()
        return True

    def on_process_start(self, feed):
        if self.parse_replaces(feed):
            feed.config = self.replace_item(feed.config)
            log.debug(feed.config)

register_plugin(CliConfig, 'cli_config', builtin=True)
register_parser_option('--cli-config', action='store', dest='cli_config', default=False,
                       metavar='PARAMS', help='Configuration parameters trough commandline. See --doc cli_config.')
