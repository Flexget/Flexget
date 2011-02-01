import os
import logging
from flexget.plugin import register_plugin, priority, PluginError, get_plugin_by_name
from flexget.feed import Entry

log = logging.getLogger('exists_movie')


class FilterExistsMovie(object):

    """
        Reject existing movies.

        Example:

        exists_movie: /storage/movies/
    """

    skip = ['cd1', 'cd2', 'subs', 'sample']

    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('path')
        bundle = root.accept('list')
        bundle.accept('path')
        return root

    def get_config(self, feed):
        config = feed.config.get('exists_movie', [])
        # if only a single path is passed turn it into a 1 element list
        if isinstance(config, basestring):
            config = [config]
        return config

    @priority(-1)
    def on_feed_filter(self, feed):
        if not feed.accepted:
            log.debug('nothing accepted, aborting')
            return
    
        config = self.get_config(feed)
        imdb_lookup = get_plugin_by_name('imdb_lookup').instance.lookup

        incompatible_dirs = 0
        incompatible_entries = 0
        count_entries = 0
        count_dirs = 0

        # list of imdb urls gathered from paths
        imdb_urls = []

        for path in config:
            path = os.path.expanduser(path)
            if not os.path.exists(path):
                log.critical('Path %s does not exist' % path)
                continue
                
            feed.verbose_progress('Scanning path %s ...' % path, log)

            # scan through
            for root, dirs, files in os.walk(path):
                # convert filelists into utf-8 to avoid unicode problems
                dirs = [x.decode('utf-8', 'ignore') for x in dirs]
                # files = [x.decode('utf-8', 'ignore') for x in files]

                # TODO: add also video files?

                for item in dirs:
                    if item.lower() in self.skip:
                        continue
                    count_dirs += 1
                    fake_entry = Entry()
                    fake_entry['title'] = item
                    fake_entry['url'] = 'file://%s/%s' % (path, item)
                    try:
                        imdb_lookup(feed, fake_entry)
                        imdb_url = fake_entry['imdb_url']
                        if imdb_url in imdb_urls:
                            log.log(5, 'duplicate %s' % fake_entry['title'])
                            continue
                        imdb_urls.append(imdb_url)
                    except PluginError, e:
                        log.log(5, '%s lookup failed (%s)' % (fake_entry['title'], e.value))
                        incompatible_dirs += 1

        log.debug('-- Start filtering entries ----------------------------------')

        # do actual filtering
        for entry in feed.accepted:
            count_entries += 1
            if not 'imdb_url' in entry:
                try:
                    imdb_lookup(feed, entry)
                except PluginError, e:
                    log.log(5, 'entry %s imdb failed (%s)' % (entry['title'], e.value))
                    incompatible_entries += 1
                    continue
            if entry['imdb_url'] in imdb_urls:
                feed.reject(entry, 'movie exists')

        if incompatible_dirs or incompatible_entries:
            feed.verbose_progress('There were some incompatible items. %s of %s entries and %s of %s directories could not be verified.' % \
                (incompatible_entries, count_entries, incompatible_dirs, count_dirs), log)

register_plugin(FilterExistsMovie, 'exists_movie', groups=['exists'])
