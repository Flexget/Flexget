import logging
from flexget.plugin import register_plugin

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
        # If only a single path is passed turn it into a 1 element list
        if isinstance(config, basestring):
            config = [config]
        return config

    def on_feed_input(self, feed):
        from flexget.feed import Entry
        import os
        config = self.get_config(feed)
        for path in config:
            for name in os.listdir(unicode(path)):
                e = Entry()
                e['title'] = name
                filepath = os.path.join(path, name)
                # Windows paths need an extra / prepended to them
                if not filepath.startswith('/'):
                    filepath = '/' + filepath
                e['url'] = 'file://%s' % (filepath)
                e['location'] = os.path.join(path, name)
                feed.entries.append(e)

register_plugin(InputListdir, 'listdir')
