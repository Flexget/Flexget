import logging

__pychecker__ = 'unusednames=parser'

log = logging.getLogger('search')

class Search:

    """
        Search entry from sites. Accepts list of known search modules, list is in priority order.
        Once hit has been found no more searches are performed. Should be used only when
        there is no other way to get working download url, ie. when input module does not provide 
        any downloadable urls.
        
        Example:
        
        search:
          - newtorrents
          - piratebay
          
        Notes: 
        - Some resolvers will use search modules automaticly if enry url points into a search page.
    """

    def register(self, manager, parser):
        manager.register('search')
        manager.add_feed_event('search', after='resolve')
        
        
    def validator(self):
        # TODO: should only accept registered search modules
        import validator
        search = validator.factory('list')
        search.accept('text')
        return search

    def feed_search(self, feed):
        # no searches in unit test mode
        if feed.manager.unit_test: 
            return 
        
        modules = {}
        for module in feed.manager.get_modules_by_group('search'):
            modules[module['name']] = module['instance']
            
        for entry in feed.entries:
            # loop trough configured searches
            for name in feed.config.get('search', []):
                if not name in modules:
                    log.error('Search modules %s not found' % name)
                    log.debug('Registered: %s' % ', '.join(modules.keys()))
                    continue
                else:
                    log.debug('Issuing search from %s' % name)
                    modules[name].search(feed, entry)