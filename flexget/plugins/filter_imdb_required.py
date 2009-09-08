import logging
from flexget.plugin import *

log = logging.getLogger('imdb_required')

class FilterImdbRequired:
    """
        Rejects entries without imdb url.

        Example:

        imdb_required: yes
    """
    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    def feed_filter(self, feed):
        for entry in feed.entries:
            try:
                get_plugin_by_name('imdb_lookup').instance.lookup(feed, entry)
            except PluginError:
                feed.reject(entry, 'imdb required')
            if not 'imdb_url' in entry:
                feed.reject(entry, 'imdb required')

register_plugin(FilterImdbRequired, 'imdb_required', priorities={'filter': 32})
