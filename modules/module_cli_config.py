import logging
import types

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

    def register(self, manager, parser):
        manager.register(instance=self, event='start', keyword='cli_config', callback=self.run, builtin=True)
        parser.add_option('--cli-config', action='store', dest='cli_config', default=False,
                          help='Configuration parameters trough commandline. See --doc cli_config.')
        self.replaces = {}        
    
    def replace_dict(self, d, replaces):
        for k,v in d.items():
            if type(v) == types.StringType:
                nv = replaces.get(v[1:], False)
                if nv and v.startswith('$'):
                    log.debug('Replacing key %s (%s -> %s)' % (k, v, nv))
                    d[k] = nv
            if type(v) == types.ListType:
                for lv in v[:]:
                    nv = replaces.get(lv[1:], False)
                    if nv and lv.startswith('$'):
                        log.debug('Replacing list item %s (%s -> %s)' % (k, lv, nv))
                        i = v.index(lv)
                        v[i] = nv
            if type(v) == types.DictType:
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
            key = item[:item.index('=')]
            value = item[item.index('=')+1:]
            self.replaces[key.strip()] = value.strip()
        return True

    def run(self, feed):
        if self.parse_replaces(feed):
            self.replace_dict(feed.config, self.replaces)
            log.debug(feed.config)


if __name__ == '__main__':
    import sys
    from test_tools import MockFeed
    import yaml
    logging.basicConfig(level=logging.DEBUG)
    feed = MockFeed()

    # make mock config
    config = {}
    config['url'] = '$url'
    values = {}
    values['url'] = 1
    values['title'] = 3
    config['values'] = '@values'
    config['array'] = ['a','b','$arr','d']
    feed.config['csv'] = config
    
    replaces = {'url':'new replaced url', 'values':'new replaced value', 'arr':'new in array'}
    
    ci = CliConfig()
    ci.replace_dict(config, replaces)

    print yaml.dump(config)
