import logging
from filter_seen import FilterSeen
from flexget.plugin import *

log = logging.getLogger('seenmovies')

class FilterSeenMovies(FilterSeen):
    """
        Prevents movies being downloaded twice.
        Works only on entries which have imdb url available.

        How duplicate movie detection works:
        1) Remember all imdb urls from downloaded entries.
        2) If stored imdb url appears again, entry is rejected.
    """

    def on_process_start(self, feed):
        """Disable this so it doesn't get ran twice"""
        pass

    def __init__(self):
        # remember and filter by these fields
        self.fields = ['imdb_url']
        self.keyword = 'seen_movies'
        
    def on_feed_filter(self, feed):
        # strict method
        if feed.config['seen_movies'] == 'strict':
            for entry in feed.entries:
                if not 'imdb_url' in entry:
                    log.info('Rejecting %s because of missing imdb url' % entry['title'])
                    feed.reject(entry, 'missing imdb url, strict')
        # call super
        super(FilterSeenMovies, self).on_feed_filter(feed)

register_plugin(FilterSeenMovies, 'seen_movies', priorities=dict(filter=64))
