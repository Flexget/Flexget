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

    @priority(-255)
    def on_feed_filter(self, feed):
        # strict method
        if feed.config['seen_movies'] == 'strict':
            for entry in feed.entries:
                if not 'imdb_url' in entry:
                    log.info('Rejecting %s because of missing imdb url' % entry['title'])
                    feed.reject(entry, 'missing imdb url, strict')
        # call super
        super(FilterSeenMovies, self).on_feed_filter(feed)
        # check that two copies of a movie have not been accepted this run
        movies = []
        for entry in feed.accepted:
            if entry.get('imdb_url'):
                if not entry['imdb_url'] in movies:
                    movies.append(entry['imdb_url'])
                else:
                    feed.reject(entry, 'already accepted once in feed')

#We run last (-255) to make sure we don't reject duplicates before all the other plugins get a chance to reject.
register_plugin(FilterSeenMovies, 'seen_movies')
