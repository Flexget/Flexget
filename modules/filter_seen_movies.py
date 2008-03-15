import urllib
import logging

log = logging.getLogger('seenmovies')

from filter_seen import FilterSeen

class FilterSeenMovies(FilterSeen):

    """
        Prevents movies being downloaded twice.
        Works only on entries which have imdb url available.

        How duplicate movie detection works:
        1) Remember all imdb urls from downloaded entries.
        2) If stored imdb url appears again, entry is rejected.
    """

    def register(self, manager, parser):
        manager.register(instance=self, event='filter', keyword='seen_movies', callback=self.filter_seen)
        manager.register(instance=self, event='exit', keyword='seen_movies', callback=self.learn_succeeded)

        # remember and filter by these fields
        self.fields = ['imdb_url']
