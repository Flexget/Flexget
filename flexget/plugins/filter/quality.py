import logging
from flexget.plugin import register_plugin, priority
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

    def prepare_config(self, feed, config):
        if not isinstance(config, dict):
            config = {'quality': config}
        if isinstance(config.get('quality'), basestring):
            config['quality'] = [config['quality']]
        return config

    # Run before series and imdb plugins, so correct qualities are chosen
    @priority(130)
    def on_feed_filter(self, feed, config):
        config = self.prepare_config(feed, config)
        for entry in feed.entries:
            if config.get('quality'):
                if not entry.get('quality') in config['quality']:
                    feed.reject(entry, 'quality is %s' % entry['quality'], remember=True)
            else:
                if config.get('min'):
                    if entry.get('quality') < config['min']:
                        feed.reject(entry, 'quality %s not >= %s' % (entry['quality'], config['min']), remember=True)
                if config.get('max'):
                    if entry.get('quality') > config['max']:
                        feed.reject(entry, 'quality %s not <= %s' % (entry['quality'], config['max']), remember=True)
register_plugin(FilterQuality, 'quality', api_ver=2)
