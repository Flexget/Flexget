import logging
from flexget.plugin import register_plugin, priority, get_plugin_by_name, PluginError

log = logging.getLogger('imdb_required')


class FilterImdbRequired(object):
    """
        Rejects entries without imdb url.

        Example:

        imdb_required: yes
    """

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    @priority(32)
    def on_feed_filter(self, feed):
        for entry in feed.entries:
            try:
                get_plugin_by_name('imdb_lookup').instance.lookup(entry)
            except PluginError:
                feed.reject(entry, 'imdb required')
            if not 'imdb_url' in entry:
                feed.reject(entry, 'imdb required')

register_plugin(FilterImdbRequired, 'imdb_required')
