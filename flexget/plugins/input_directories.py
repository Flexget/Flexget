import logging
from flexget.feed import Entry
from flexget.plugin import *

log = logging.getLogger('input_mock')

class InputDirectories:
    """
        Uses local path as input
        
        Example:
        
        directories: /storage/movies/
    """
    def validator(self):
        from flexget import validator
        return validator.factory('path')

    def on_feed_input(self, feed):
        import os
        
        for name in os.listdir(feed.config['directories']):
            e = Entry()
            e['title'] = name
            e['url'] = 'file://%s/%s' % (feed.config['directories'], dir)
            
            feed.entries.append(e)

register_plugin(InputDirectories, 'directories')
