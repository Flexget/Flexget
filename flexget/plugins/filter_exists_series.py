import os
import logging
from flexget.plugin import *
from flexget.utils.titles import SeriesParser

log = logging.getLogger('exists_series')

class FilterExistsSeries:
    """
        Intelligent series aware exists rejecting.

        Example:

        exists_series: /storage/series/
    """
    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('path')
        bundle = root.accept('list')
        bundle.accept('path')
        return root
        
    def get_config(self, feed):
        config = feed.config.get('exists_series', [])
        # if only a single path is passed turn it into a 1 element list
        if isinstance(config, basestring):
            config = [config]
        return config

    def on_feed_filter(self, feed):
        config = self.get_config(feed)
        for path in config:
            path = os.path.expanduser(path)
            if not os.path.exists(path):
                raise PluginWarning('Path %s does not exist' % path, log)
            # scan through
            for root, dirs, files in os.walk(path):
                # convert filelists into utf-8 to avoid unicode problems
                dirs = [x.decode('utf-8', 'ignore') for x in dirs]
                files = [x.decode('utf-8', 'ignore') for x in files]
                for entry in feed.entries:
                    if 'series_parser' in entry:
                        for name in files + dirs:
                            # make new parser from parser in entry
                            parser = SeriesParser()
                            oldparser = entry['series_parser']
                            parser.name = oldparser.name
                            parser.ep_regexps = oldparser.ep_regexps
                            parser.id_regexps = oldparser.id_regexps
                            # run parser on filename data
                            parser.data = name
                            parser.parse()
                            if parser.valid:
                                log.debug('name %s is same series as %s' % (name, entry['title']))
                                log.debug('parser.identifier = %s' % parser.identifier())
                                log.debug('oldparser.identifier = %s' % oldparser.identifier())
                                log.debug('parser.quality = %s' % parser.quality)
                                log.debug('oldparser.quality = %s' % oldparser.quality)
                                
                                if parser.identifier() == oldparser.identifier() and \
                                   parser.quality == oldparser.quality:
                                    log.debug('Found episode %s %s in %s' % (parser.name, parser.identifier(), root))
                                    feed.reject(entry, 'episode already exists')
                                else:
                                    log.debug('... but doesn\'t match')
                    else:
                        log.debug('%s doesn\'t seem to be a series' % entry['title'])

register_plugin(FilterExistsSeries, 'exists_series', groups=['exists'], priorities={'filter': -1})
