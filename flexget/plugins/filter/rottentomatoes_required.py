import logging
from flexget.plugin import register_plugin, priority, get_plugin_by_name, PluginError

log = logging.getLogger('rottentomatoes_required')


class FilterRottenTomatoesRequired(object):
    """
    Rejects entries without rt_url or rt_id.
    Makes Rotten Tomatoes lookup / search if necessary.

    Example:

    rottentomatoes_required: yes
    """

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    @priority(32)
    def on_feed_filter(self, feed):
        for entry in feed.entries:
            try:
                get_plugin_by_name('rottentomatoes_lookup').instance.lookup(entry)
            except PluginError:
                feed.reject(entry, 'rotten tomatoes required')
            if 'rt_url' not in entry and 'rt_id' not in entry:
                feed.reject(entry, 'rotten tomatoes required')

register_plugin(FilterRottenTomatoesRequired, 'rottentomatoes_required')
