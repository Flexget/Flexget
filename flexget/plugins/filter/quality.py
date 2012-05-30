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

        root = validator.factory()
        root.accept('quality_requirements')
        root.accept('list').accept('quality_requirements')
        return root

    # Run before series and imdb plugins, so correct qualities are chosen
    @priority(175)
    def on_feed_filter(self, feed, config):
        if not isinstance(config, list):
            config = [config]
        reqs = [quals.Requirements(req) for req in config]
        for entry in feed.entries:
            if not entry.get('quality'):
                feed.reject(entry, 'Entry doesn\'t have a quality')
                continue
            if not any(req.allows(entry['quality']) for req in reqs):
                feed.reject(entry, '%s does not match quality requirement %s' % (entry['quality'], reqs))

register_plugin(FilterQuality, 'quality', api_ver=2)
