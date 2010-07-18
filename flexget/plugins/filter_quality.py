import logging
from flexget.plugin import *
import flexget.utils.qualities as quals

log = logging.getLogger('quality')


class FilterQuality(object):
    """
        Rejects all entries that don't have one of the specified qualities
        
        Example:
        
        quality:
          - hdtv
    """

    def validator(self):
        from flexget import validator

        qualities = [q.name for q in quals.all()]

        root = validator.factory()
        root.accept('choice').accept_choices(qualities, ignore_case=True)
        root.accept('list').accept('choice').accept_choices(qualities, ignore_case=True)
        advanced = root.accept('dict')
        advanced.accept('choice', key='min').accept_choices(qualities, ignore_case=True)
        advanced.accept('choice', key='max').accept_choices(qualities, ignore_case=True)
        advanced.accept('choice', key='quality').accept_choices(qualities, ignore_case=True)
        advanced.accept('list', key='quality').accept('choice').accept_choices(qualities, ignore_case=True)
        return root

    def get_config(self, feed):
        config = feed.config.get('quality', None)
        if not isinstance(config, dict):
            config = {'quality': config}
        if isinstance(config.get('quality'), basestring):
            config['quality'] = [config['quality']]
        return config

    def on_feed_filter(self, feed):
        config = self.get_config(feed)
        for entry in feed.entries:
            if config.get('quality'):
                if not quals.get(entry.get('quality')) in [quals.get(q) for q in config['quality']]:
                    feed.reject(entry, 'quality is %s' % entry['quality'])
            else:
                if config.get('min'):
                    if not quals.get(entry.get('quality')) >= quals.get(config['min']):
                        feed.reject(entry, 'quality %s not >= %s' % (entry['quality'], config['min']))
                if config.get('max'):
                    if not quals.get(entry.get('quality')) <= quals.get(config['max']):
                        feed.reject(entry, 'quality %s not <= %s' % (entry['quality'], config['max']))
register_plugin(FilterQuality, 'quality')
