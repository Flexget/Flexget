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
        return validator.factory('path')

    def on_feed_input(self, feed):
        from flexget.feed import Entry
        import os
        for name in os.listdir(feed.config['listdir']):
            e = Entry()
            e['title'] = name
            e['url'] = 'file://%s' % (os.path.join(feed.config['listdir'], name))
            e['location'] = os.path.join(feed.config['listdir'], name)
            feed.entries.append(e)

register_plugin(InputListdir, 'listdir')
