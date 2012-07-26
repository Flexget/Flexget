import logging
from flexget.plugin import register_plugin, priority

log = logging.getLogger('require_field')


class FilterRequireField(object):
    """
    Rejects entries without imdb url.

    Example::

      require_field: imdb_url
    """

    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('text')
        root.accept('list').accept('text')
        return root

    @priority(32)
    def on_feed_filter(self, feed, config):
        if isinstance(config, basestring):
            config = [config]
        for entry in feed.entries:
            for field in config:
                if not entry.get(field):
                    feed.reject(entry, 'Required field %s is not present' % field)
                    break


register_plugin(FilterRequireField, 'require_field', api_ver=2)
