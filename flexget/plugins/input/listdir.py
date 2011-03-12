"""Plugin for filesystem feeds."""
import logging
from flexget import plugin

log = logging.getLogger('listdir')


class Listdir(plugin.Plugin):
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

    def on_feed_input(self, feed, config):
        from flexget.feed import Entry
        import os
        # If only a single path is passed turn it into a 1 element list
        if isinstance(config, basestring):
            config = [config]
        entries = []
        for path in config:
            for name in os.listdir(unicode(path)):
                e = Entry()
                e['title'] = name
                filepath = os.path.join(path, name)
                # Windows paths need an extra / preceded to them
                if not filepath.startswith('/'):
                    filepath += '/'
                e['url'] = 'file://%s' % filepath
                e['location'] = os.path.join(path, name)
                entries.append(e)
        return entries
