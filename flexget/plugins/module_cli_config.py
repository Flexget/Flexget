import logging
from flexget.plugin import *

log = logging.getLogger('cli_config')

class CliConfig:

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

    def validator(self):
        # there is no way to misconfigure this .. 
        from flexget import validator
        return validator.factory('any')
    
    def replace_dict(self, d, replaces):
        for k,v in d.items():
            if isinstance(v, basestring):
                nv = replaces.get(v[1:], False)
                if nv and v.startswith('$'):
                    log.debug('Replacing key %s (%s -> %s)' % (k, v, nv))
                    d[k] = nv
            if isinstance(v, list):
                for lv in v[:]:
                    if isinstance(lv, dict):
                        self.replace_dict(lv, replaces)
                    else:
                        nv = replaces.get(lv[1:], False)
                        if nv and lv.startswith('$'):
                            log.debug('Replacing list item %s (%s -> %s)' % (k, lv, nv))
                            i = v.index(lv)
                            v[i] = nv
            if isinstance(v, dict):
                self.replace_dict(v, replaces)

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
            value = item[item.index('=')+1:]
            self.replaces[key.strip()] = value.strip()
        return True

    def feed_start(self, feed):
        if self.parse_replaces(feed):
            self.replace_dict(feed.config, self.replaces)
            log.debug(feed.config)

register_plugin(CliConfig, 'cli_config', builtin=True)
register_parser_option('--cli-config', action='store', dest='cli_config', default=False,
                       metavar='PARAMS', help='Configuration parameters trough commandline. See --doc cli_config.')
