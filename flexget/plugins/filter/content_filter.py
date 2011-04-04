import logging
from flexget.plugin import register_plugin, priority
from flexget.utils.log import log_once
from fnmatch import fnmatch

log = logging.getLogger('content_filter')


class FilterContentFilter(object):
    """
    Rejects entries based on the filenames in the content. Torrent files only right now.

    Example:
    content_filter:
      require:
        - '*.avi'
        - '*.mkv'
    """

    def validator(self):
        from flexget import validator
        config = validator.factory('dict')
        config.accept('text', key='require')
        config.accept('list', key='require').accept('text')
        config.accept('text', key='reject')
        config.accept('list', key='reject').accept('text')
        config.accept('boolean', key='strict')
        return config

    def get_config(self, feed):
        config = feed.config.get('content_filter')
        for key in ['require', 'reject']:
            if key in config:
                if isinstance(config[key], basestring):
                    config[key] = [config[key]]
        return config

    def process_entry(self, feed, entry):
        config = self.get_config(feed)
        if 'content_files' in entry:
            files = entry['content_files']
            log.debug('%s files: %s' % (entry['title'], files))

            def matching_mask(files, masks):
                """Returns matching mask if any files match any of the masks, false otherwise"""
                for file in files:
                    for mask in masks:
                        if fnmatch(file, mask):
                            return mask
                return False

            # Avoid confusion by printing a reject message to info log, as
            # download plugin has already printed a downloading message.
            if config.get('require'):
                if not matching_mask(files, config['require']):
                    log_once('Entry %s does not have any of the required filetypes, rejecting' % entry['title'], log)
                    feed.reject(entry, 'does not have any of the required filetypes', remember=True)
            if config.get('reject'):
                mask = matching_mask(files, config['reject'])
                if mask:
                    log_once('Entry %s has banned file %s, rejecting' % (entry['title'], mask), log)
                    feed.reject(entry, 'has banned file %s' % mask, remember=True)

    def parse_torrent_files(self, entry):
        if 'torrent' in entry:
            files = [item['name'] for item in entry['torrent'].get_filelist()]
            if files:
                entry['content_files'] = files

    @priority(150)
    def on_feed_modify(self, feed):
        if feed.manager.options.test or feed.manager.options.learn:
            log.info('Plugin is partially disabled with --test and --learn because content filename information may not be available')
            return

        config = self.get_config(feed)
        for entry in feed.accepted:
            # TODO: I don't know if we can pares filenames from nzbs, just do torrents for now
            # possibly also do compressed files in the future
            self.parse_torrent_files(entry)
            self.process_entry(feed, entry)
            if not 'content_files' in entry and config.get('strict'):
                feed.reject(entry, 'no content files parsed for entry', remember=True)

register_plugin(FilterContentFilter, 'content_filter')
