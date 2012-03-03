import logging
from flexget.plugin import register_plugin

log = logging.getLogger('sort_by')


class PluginSortBy:

    """
        Sort feed entries based on a field

        Example:

        sort_by: title

        More complex:

        sort_by:
          field: imdb_score
          reverse: yes

        Reverse the order of the entries, without sorting on a field:

        sort_by:
            reverse: yes
    """

    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('text')
        complex = root.accept('dict')
        # TODO: accept a list of fields.
        complex.accept('text', key='field')
        complex.accept('boolean', key='reverse')
        return root

    def on_feed_filter(self, feed, config):
        if isinstance(config, basestring):
            field = config
            reverse = False
        else:
            field = config.get('field', None)
            reverse = config.get('reverse', False)

        log.debug('sorting entries by: %s' % config)

        if not field:
            feed.entries.reverse()
            feed.accepted.reverse()
            return

        def cmp_helper(a, b):
            va = a.get(field, 0)
            vb = b.get(field, 0)
            return cmp(va, vb)

        feed.entries.sort(cmp_helper, reverse=reverse)
        feed.accepted.sort(cmp_helper, reverse=reverse)

register_plugin(PluginSortBy, 'sort_by', api_ver=2)
