import logging
from flexget.plugin import *

log = logging.getLogger('listdir')


class InputListdir:
    """
        Uses local path content as an input.
        
        Example:
        
        listdir: /storage/movies/
    """
    
    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('path')
        bundle = root.accept('list')
        bundle.accept('path')
        return root
        
    def get_config(self, feed):
        config = feed.config.get('listdir', None)
        #if only a single path is passed turn it into a 1 element list
        if isinstance(config, basestring):
            config = [config]
        return config

    def on_feed_input(self, feed):
        from flexget.feed import Entry
        import os
        config = self.get_config(feed)
        for path in config: 
            for name in os.listdir(path):
                e = Entry()
                e['title'] = name
                e['url'] = 'file://%s' % (os.path.join(path, name))
                e['location'] = os.path.join(path, name)
                feed.entries.append(e)

register_plugin(InputListdir, 'listdir')
