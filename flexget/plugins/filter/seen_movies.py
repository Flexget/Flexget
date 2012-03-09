import logging
from flexget.plugins.filter.seen import FilterSeen
from flexget.plugin import register_plugin, priority

log = logging.getLogger('seenmovies')


class FilterSeenMovies(FilterSeen):
    """
        Prevents movies being downloaded twice.
        Works only on entries which have imdb url available.

        How duplicate movie detection works:
        1) Remember all imdb urls from downloaded entries.
        2) If stored imdb url appears again, entry is rejected.
    """

    def __init__(self):
        # remember and filter by these fields
        self.fields = ['imdb_id', 'tmdb_id']
        self.keyword = 'seen_movies'

    def validator(self):
        from flexget import validator
        root = validator.factory('choice', message="must be one of the following: strict, loose")
        root.accept_choices(['strict', 'loose'])
        return root

    # We run last (-255) to make sure we don't reject duplicates before all the other plugins get a chance to reject.
    @priority(-255)
    def on_feed_filter(self, feed, config):
        # strict method
        if config == 'strict':
            for entry in feed.entries:
                if 'imdb_id' not in entry and 'tmdb_id' not in entry:
                    log.info('Rejecting %s because of missing movie (imdb or tmdb) id' % entry['title'])
                    feed.reject(entry, 'missing movie (imdb or tmdb) id, strict')
        # call super
        super(FilterSeenMovies, self).on_feed_filter(feed, True)
        # check that two copies of a movie have not been accepted this run
        imdb_ids = set()
        tmdb_ids = set()
        for entry in feed.accepted:
            if 'imdb_id' in entry:
                if entry['imdb_id'] in imdb_ids:
                    feed.reject(entry, 'already accepted once in feed')
                    continue
                else:
                    imdb_ids.add(entry['imdb_id'])
            if 'tmdb_id' in entry:
                if entry['tmdb_id'] in tmdb_ids:
                    feed.reject(entry, 'already accepted once in feed')
                    continue
                else:
                    tmdb_ids.add(entry['tmdb_id'])

register_plugin(FilterSeenMovies, 'seen_movies', api_ver=2)
