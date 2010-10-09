import os
import logging
from flexget.plugin import *
from flexget.utils.titles import SeriesParser, ParseWarning

log = logging.getLogger('exists_series')


class FilterExistsSeries(object):
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
        advform = root.accept('dict')
        advform.accept('boolean', key='allow_different_qualities')
        advform.accept('path', key='path')
        advform.accept('list', key='path').accept('path')
        return root
        
    def get_config(self, feed):
        config = feed.config.get('exists_series', [])
        # if config is not a dict, assign value to 'path' key
        if not isinstance(config, dict):
            config = {'path': config}
        # if only a single path is passed turn it into a 1 element list
        if isinstance(config['path'], basestring):
            config['path'] = [config['path']]
        return config

    @priority(-1)
    def on_feed_filter(self, feed):
        for entry in feed.accepted:
            if 'series_parser' in entry:
                break
        else:
            if feed.accepted:
                log.warning('No accepted entries have series information. exists_series cannot filter them')
            else:
                log.debug('Scanning not needed')
            return
    
        config = self.get_config(feed)
        for path in config.get('path'):
            feed.verbose_progress('Scanning %s' % path, log)
            path = os.path.expanduser(path)
            if not os.path.exists(path):
                raise PluginWarning('Path %s does not exist' % path, log)
            # scan through
            for root, dirs, files in os.walk(path):
                # convert filelists into utf-8 to avoid unicode problems
                dirs = [x.decode('utf-8', 'ignore') for x in dirs]
                files = [x.decode('utf-8', 'ignore') for x in files]
                # For speed, only test accepted entries since our priority should be after everything is accepted.
                for entry in feed.accepted:
                    if 'series_parser' in entry:
                        for name in files + dirs:
                            # make new parser from parser in entry
                            disk_parser = SeriesParser()
                            series_parser = entry['series_parser']
                            disk_parser.name = series_parser.name
                            disk_parser.strict_name = series_parser.strict_name
                            disk_parser.ep_regexps = series_parser.ep_regexps
                            disk_parser.id_regexps = series_parser.id_regexps
                            # run parser on filename data
                            disk_parser.data = name
                            try:
                                disk_parser.parse()
                            except ParseWarning, pw:
                                from flexget.utils.log import log_once
                                log_once(pw.value, logger=log)
                            if disk_parser.valid:
                                log.debug('name %s is same series as %s' % (name, entry['title']))
                                log.debug('disk_parser.identifier = %s' % disk_parser.identifier)
                                log.debug('series_parser.identifier = %s' % series_parser.identifier)
                                log.debug('disk_parser.quality = %s' % disk_parser.quality)
                                log.debug('series_parser.quality = %s' % series_parser.quality)
                                log.debug('disk_parser.proper = %s' % disk_parser.proper)
                                log.debug('series_parser.proper = %s' % series_parser.proper)
                                
                                if disk_parser.identifier != series_parser.identifier:
                                    log.log(5, 'wrong identifier')
                                    continue
                                if config.get('allow_different_qualities') and disk_parser.quality != series_parser.quality:
                                    log.log(5, 'wrong quality')
                                    continue
                                if disk_parser.proper and not series_parser.proper:
                                    feed.reject(entry, 'proper already exists')
                                    continue
                                if series_parser.proper and not disk_parser.proper:
                                    log.log(5, 'new one is proper, disk is not')
                                    continue
                                
                                feed.reject(entry, 'episode already exists')    
                    else:
                        log.log(5, '%s doesn\'t seem to be known series' % entry['title'])

register_plugin(FilterExistsSeries, 'exists_series', groups=['exists'])
