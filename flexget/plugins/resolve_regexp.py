import re
import logging
import yaml
from flexget.plugin import *

log = logging.getLogger('regexp')

class ResolveRegexp:
    """
        Generic regexp resolver.
        
        Example:
        
        regexp_resolve:
          demonoid:
            match: http://www.demonoid.com/files/details/
            replace: http://www.demonoid.com/files/download/HTTP/
    """

    resolves = {}

    # built-in resolves
    
#    resolves = yaml.safe_load("""
#    tvsubtitles:
#      match: http://www.tvsubtitles.net/subtitle-
#      replace: http://www.tvsubtitles.net/download-
#    """
#    )

    def validator(self):
        from flexget import validator
        root = validator.factory('dict')
        config = root.accept_any_key('dict')
        config.accept('regexp', key='match', required=True)
        config.accept('regexp', key='replace', required=True)
        return root
    
    def process_start(self, feed):
        for name, config in feed.config.get('regexp_resolve', {}).iteritems():
            match = re.compile(config['match'])
            replace =  config['replace']
            self.resolves[name] = {'match': match, 'replace': replace }
            log.debug('Added regexp resolve %s' % name)

    def resolvable(self, feed, entry):
        for name, config in self.resolves.iteritems():
            if config['match'].match(entry['url']):
                return True
        return False
        
    def resolve(self, feed, entry):
        for name, config in self.resolves.iteritems():
            if config['match'].match(entry['url']):
                log.debug('Regexp resolving %s with %s' % (entry['url'], name))
                entry['url'] = config['match'].sub(config['replace'], entry['url'])
                if config['match'].match(entry['url']):
                    from module_resolver import ResolverException
                    raise ResolverException('Regexp %s replace result should NOT continue to match!' % name)
                return

register_plugin(ResolveRegexp, 'regexp_resolve', groups=['resolver'])
