import logging
from flexget.plugin import register_plugin, DependencyError, PluginError
from flexget.utils import imdb
from flexget.utils.log import log_once

try:
    from flexget.plugins.api_rottentomatoes import lookup_movie
except ImportError:
    raise DependencyError(issued_by='rottentomatoes_lookup', missing='api_rottentomatoes',
                          message='rottentomatoes_lookup requires the `api_rottentomatoes` plugin')

log = logging.getLogger('rottentomatoes_lookup')


class PluginRottenTomatoesLookup(object):
    """Retrieves Rotten Tomatoes information for entries.

    Example:
        rottentomatoes_lookup: yes
    """

    field_map = {
        'rt_name': 'title',
        'rt_id': 'id',
        'imdb_id': lambda movie: ('tt' + filter(lambda alt_id: alt_id.name == 'imdb',
            movie.alternate_ids)[0].id) if filter(lambda alt_id: alt_id.name ==
                'imdb', movie.alternate_ids) else None,
        'rt_year': 'year',
        'rt_genres': lambda movie: movie.genres and [genre.name for genre in movie.genres],
        'rt_mpaa_rating': 'mpaa_rating',
        'rt_runtime': 'runtime',
        'rt_critics_consensus': 'critics_consensus',
        'rt_releases': lambda movie: movie.release_dates and dict((release.name, release.date) for
            release in movie.release_dates),
        'rt_critics_rating': 'critics_rating',
        'rt_critics_score': 'critics_score',
        'rt_audience_rating': 'audience_rating',
        'rt_audience_score': 'audience_score',
        'rt_average_score': lambda movie: (movie.critics_score + movie.audience_score) / 2,
        'rt_synopsis': 'synopsis',
        'rt_posters': lambda movie: movie.posters and dict((poster.name, poster.url) for poster in movie.posters),
        'rt_actors': lambda movie: movie.cast and [actor.name for actor in movie.cast],
        'rt_directors': lambda movie: movie.directors and [director.name for director in movie.directors],
        'rt_studio': 'studio',
        'rt_alternate_ids': lambda movie: movie.alternate_ids and (dict((alt_id.name, alt_id.id)
            for alt_id in movie.alternate_ids)),
        'rt_url': lambda movie: movie.links and filter(lambda link: link.name == 'alternate',
            movie.links)[0].url,
        # Generic fields filled by all movie lookup plugins:
        'movie_name': 'title',
        'movie_year': 'year'}

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    def lazy_loader(self, entry, field):
        """Does the lookup for this entry and populates the entry fields.

        :param entry: entry to perform lookup on
        :param field: the field to be populated (others may be populated as well)
        :returns: the field value

        """
        try:
            self.lookup(entry)
        except PluginError as e:
            log_once(e.value.capitalize(), logger=log)
            # Set all of our fields to None if the lookup failed
            entry.unregister_lazy_fields(self.field_map, self.lazy_loader)
        return entry[field]

    def lookup(self, entry, search_allowed=True):
        """
        Perform Rotten Tomatoes lookup for entry.

        :param entry: Entry instance
        :param search_allowed: Allow fallback to search
        :raises PluginError: Failure reason
        """
        imdb_id = entry.get('imdb_id', eval_lazy=False) or \
                  imdb.extract_id(entry.get('imdb_url', eval_lazy=False))
        if imdb_id:
            movie = lookup_movie(title=entry.get('imdb_name'),
                                 year=entry.get('imdb_year'),
                                 rottentomatoes_id=entry.get('rt_id', eval_lazy=False),
                                 imdb_id=imdb_id,
                                 only_cached=(not search_allowed))
        else:
            movie = lookup_movie(smart_match=entry['title'],
                                 rottentomatoes_id=entry.get('rt_id', eval_lazy=False),
                                 only_cached=(not search_allowed))
        log.debug(u'Got movie: %s' % movie)
        entry.update_using_map(self.field_map, movie)

    def on_task_metainfo(self, task, config):
        if not config:
            return
        for entry in task.entries:
            entry.register_lazy_fields(self.field_map, self.lazy_loader)

register_plugin(PluginRottenTomatoesLookup, 'rottentomatoes_lookup', api_ver=2)
