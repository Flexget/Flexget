import logging
from flexget.plugin import *

log = logging.getLogger('sort_by')

class ModuleSortBy:

    """
        Sort feed entries based on a field
    
        Example:

        sort_by: title
        
        More complex:
        
        sort_by:
          field: imdb_score
          reverse: yes
    """
    
    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('text')
        complex = root.accept('dict')
        complex.accept('text', key='field', required=True)
        complex.accept('boolean', key='reverse')
        return root

    def feed_modify(self, feed):
        if isinstance(feed.config['sort_by'], basestring):
            field = feed.config['sort_by']
            revert = False
        else:
            field = feed.config['sort_by'].get('field', 'title')
            revert = feed.config['sort_by'].get('reverse', False)
            
        config = feed.config['sort_by']
        log.debug('sorting entries by: %s' % config)
        
        def cmp_helper(a, b):
            va = a.get(field, 0)
            vb = b.get(field, 0)
            return cmp(va, vb)
        
        feed.entries.sort(cmp_helper, reverse=revert)
        feed.accepted.sort(cmp_helper, reverse=revert)
            
register_plugin(ModuleSortBy, 'sort_by')
