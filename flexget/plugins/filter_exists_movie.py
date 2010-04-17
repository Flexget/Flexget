import os
import logging
from flexget.plugin import *
from flexget.utils.titles import SeriesParser
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
        config = self.get_config(feed)
        imdb_lookup = get_plugin_by_name('imdb_lookup').instance.lookup
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
                    if not 'imdb_url' in entry:
                        imdb_lookup(feed, entry)
                    if 'imdb_url' in entry:
                        for item in dirs:
                            if item.lower() in self.skip:
                                continue
                            fake_entry = Entry()
                            fake_entry['title'] = item
                            fake_entry['url'] = 'file://%s/%s' % (path, item)
                            imdb_lookup(feed, fake_entry)
                            if not 'imdb_url' in fake_entry:
                                log.debug('fake_entry %s is not imdb compatible' % entry['title'])
                            if fake_entry.get('imdb_url') == entry['imdb_url']:
                                feed.reject('movie exists')
                    else:
                        log.debug('entry %s is not imdb compatible' % entry['title'])

register_plugin(FilterExistsMovie, 'exists_movie', groups=['exists'])
