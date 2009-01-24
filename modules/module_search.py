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

    def feed_search(self, feed):
        if feed.unittest: return # no searches in unittest mode
        
        modules = {}
        for m in feed.manager.get_modules_by_group('search'):
            modules[m['name']] = m['instance']
        
        for entry in feed.entries:
            # loop trough configured searches
            for name in feed.config.get('search', []):
                m[name].search(feed, entry)