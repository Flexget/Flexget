import logging
from flexget import plugin, validator

log = logging.getLogger('metainfo_feed')


class MetainfoFeed(plugin.BuiltinPlugin):
    """
    Utility:

    Set feed attribute for entries.
    """

    def validator(self):
        return validator.factory('boolean')

    def on_feed_metainfo(self, feed, config):
        # check if explicitely disabled (value set to false)
        if config is False:
            return

        for entry in feed.entries:
            entry['feed'] = feed.name
