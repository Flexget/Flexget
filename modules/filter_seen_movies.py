import logging
from filter_seen import FilterSeen

__pychecker__ = 'unusednames=parser'

log = logging.getLogger('seenmovies')

class FilterSeenMovies(FilterSeen):

    """
        Prevents movies being downloaded twice.
        Works only on entries which have imdb url available.

        How duplicate movie detection works:
        1) Remember all imdb urls from downloaded entries.
        2) If stored imdb url appears again, entry is rejected.
    """

    def register(self, manager, parser):
        manager.register('seen_movies')

        # remember and filter by these fields
        self.fields = ['imdb_url']
        
        # Note: our hookup methods are in FilterSeen
