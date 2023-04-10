from dateutil.parser import parse as dateutil_parse
from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.utils.tools import TimedDict

from . import db

logger = logger.bind(name=__name__)

USER_CACHE_DURATION = '15 minutes'  # cache duration for sync data eg. history, collection


class TraktUserCache(TimedDict):
    def __init__(self, cache_time):
        super().__init__(cache_time=cache_time)
        self.updaters = {
            'collection': self._update_collection_cache,
            'watched': self._update_watched_cache,
            'ratings': self._update_ratings_cache,
        }

    def _get_user_cache(self, username=None, account=None):
        identifier = '{}|{}'.format(account, username or 'me')
        self.setdefault(identifier, {}).setdefault('watched', {}).setdefault('shows', {})
        self.setdefault(identifier, {}).setdefault('watched', {}).setdefault('movies', {})
        self.setdefault(identifier, {}).setdefault('collection', {}).setdefault('shows', {})
        self.setdefault(identifier, {}).setdefault('collection', {}).setdefault('movies', {})
        self.setdefault(identifier, {}).setdefault('ratings', {}).setdefault('shows', {})
        self.setdefault(identifier, {}).setdefault('ratings', {}).setdefault('seasons', {})
        self.setdefault(identifier, {}).setdefault('ratings', {}).setdefault('episodes', {})
        self.setdefault(identifier, {}).setdefault('ratings', {}).setdefault('movies', {})

        return self[identifier]

    def _update_collection_cache(self, cache, media_type, username=None, account=None):
        collection = db.get_user_data(
            data_type='collection',
            media_type=media_type,
            session=db.get_session(account),
            username=username,
        )

        for media in collection:
            media_id = media['ids']['trakt']
            cache[media_id] = media
            collected_at = media.get('collected_at') or media.get('last_collected_at')
            cache[media_id]['collected_at'] = dateutil_parse(collected_at, ignoretz=True)

    def _update_watched_cache(self, cache, media_type, username=None, account=None):
        watched = db.get_user_data(
            data_type='watched',
            media_type=media_type,
            session=db.get_session(account),
            username=username,
        )
        for media in watched:
            media_id = media['ids']['trakt']
            cache[media_id] = media
            cache[media_id]['watched_at'] = dateutil_parse(media['last_watched_at'], ignoretz=True)
            cache[media_id]['plays'] = media['plays']

    def _update_ratings_cache(self, cache, media_type, username=None, account=None):
        ratings = db.get_user_data(
            data_type='ratings',
            media_type=media_type,
            session=db.get_session(account=account),
            username=username,
        )
        for media in ratings:
            # get the proper cache from the type returned by trakt
            media_id = media['ids']['trakt']
            cache[media_id] = media
            cache[media_id]['rated_at'] = dateutil_parse(media['rated_at'], ignoretz=True)
            cache[media_id]['rating'] = media['rating']

    def _get_data(self, data_type, media_type, username=None, account=None):
        cache = self._get_user_cache(username=username, account=account)[data_type][media_type]

        if not cache:
            logger.debug('No {} found in cache. Refreshing.', data_type)
            self.updaters[data_type](cache, media_type, username=username, account=account)
            cache = self._get_user_cache(username=username, account=account)[data_type][media_type]

        if not cache:
            logger.warning('No {} data returned from trakt.', data_type)

        return cache

    def get_shows_collection(self, username=None, account=None):
        return self._get_data('collection', 'shows', username=username, account=account)

    def get_movie_collection(self, username=None, account=None):
        return self._get_data('collection', 'movies', username=username, account=account)

    def get_watched_shows(self, username=None, account=None):
        return self._get_data('watched', 'shows', username=username, account=account)

    def get_watched_movies(self, username=None, account=None):
        return self._get_data('watched', 'movies', username=username, account=account)

    def get_show_user_ratings(self, username=None, account=None):
        return self._get_data('ratings', 'shows', username=username, account=account)

    def get_season_user_ratings(self, username=None, account=None):
        return self._get_data('ratings', 'seasons', username=username, account=account)

    def get_episode_user_ratings(self, username=None, account=None):
        return self._get_data('ratings', 'episodes', username=username, account=account)

    def get_movie_user_ratings(self, username=None, account=None):
        return self._get_data('ratings', 'movies', username=username, account=account)


# Global user cache
# TODO better idea?
user_cache = TraktUserCache(cache_time=USER_CACHE_DURATION)


class ApiTrakt:
    def __init__(self, username=None, account=None):
        self.account = account
        self.username = db.get_username(username, account)

    @property
    def lookup_map(self):
        return {
            'watched': {
                'show': self.is_show_watched,
                'season': self.is_season_watched,
                'episode': self.is_episode_watched,
                'movie': self.is_movie_watched,
            },
            'collected': {
                'show': self.is_show_in_collection,
                'season': self.is_season_in_collection,
                'episode': self.is_episode_in_collection,
                'movie': self.is_movie_in_collection,
            },
            'ratings': {
                'show': self.show_user_ratings,
                'season': self.season_user_ratings,
                'episode': self.episode_user_ratings,
                'movie': self.movie_user_ratings,
            },
        }

    @staticmethod
    def lookup_series(session, title=None, year=None, only_cached=None, **lookup_params):
        trakt_show_ids = db.TraktShowIds(**lookup_params)
        series = db.get_item_from_cache(
            db.TraktShow, title=title, year=year, trakt_ids=trakt_show_ids, session=session
        )
        found = None
        if not series and title:
            found = (
                session.query(db.TraktShowSearchResult)
                .filter(db.TraktShowSearchResult.search == title.lower())
                .first()
            )
            if found and found.series:
                logger.debug(
                    'Found {} in previous search results as {}', title, found.series.title
                )
                series = found.series
        if only_cached:
            if series:
                return series
            raise LookupError('Series %s not found from cache' % lookup_params)
        if series and not series.expired:
            return series
        try:
            trakt_show = db.get_trakt_data(
                'show', title=title, year=year, trakt_ids=trakt_show_ids
            )
        except LookupError as e:
            if series:
                logger.debug('Error refreshing show data from trakt, using cached. {}', e)
                return series
            raise
        try:
            series = session.merge(db.TraktShow(trakt_show, session))
            if series and title.lower() == series.title.lower():
                return series
            elif series and title and not found:
                if (
                    not session.query(db.TraktShowSearchResult)
                    .filter(db.TraktShowSearchResult.search == title.lower())
                    .first()
                ):
                    logger.debug('Adding search result to db')
                    session.merge(db.TraktShowSearchResult(search=title, series=series))
            elif series and found:
                logger.debug('Updating search result in db')
                found.series = series
            return series
        finally:
            session.commit()

    @staticmethod
    def lookup_movie(session, title=None, year=None, only_cached=None, **lookup_params):
        trakt_movie_ids = db.TraktMovieIds(**lookup_params)
        movie = db.get_item_from_cache(
            db.TraktMovie, title=title, year=year, trakt_ids=trakt_movie_ids, session=session
        )
        found = None
        if not movie and title:
            found = (
                session.query(db.TraktMovieSearchResult)
                .filter(db.TraktMovieSearchResult.search == title.lower())
                .first()
            )
            if found and found.movie:
                logger.debug('Found {} in previous search results as {}', title, found.movie.title)
                movie = found.movie
        if only_cached:
            if movie:
                return movie
            raise LookupError('Movie %s not found from cache' % lookup_params)
        if movie and not movie.expired:
            return movie
        # Parse the movie for better results
        parsed_title = None
        y = year
        if title:
            title_parser = plugin.get('parsing', 'api_trakt').parse_movie(title)
            y = year or title_parser.year
            parsed_title = title_parser.name
        try:
            trakt_movie = db.get_trakt_data(
                'movie', title=parsed_title, year=y, trakt_ids=trakt_movie_ids
            )
        except LookupError as e:
            if movie:
                logger.debug('Error refreshing movie data from trakt, using cached. {}', e)
                return movie
            raise
        try:
            movie = session.merge(db.TraktMovie(trakt_movie, session))
            if movie and title.lower() == movie.title.lower():
                return movie
            if movie and title and not found:
                if (
                    not session.query(db.TraktMovieSearchResult)
                    .filter(db.TraktMovieSearchResult.search == title.lower())
                    .first()
                ):
                    logger.debug('Adding search result to db')
                    session.merge(db.TraktMovieSearchResult(search=title, movie=movie))
            elif movie and found:
                logger.debug('Updating search result in db')
                found.movie = movie
            return movie
        finally:
            session.commit()

    def is_show_in_collection(self, trakt_data, title):
        cache = user_cache.get_shows_collection(self.username, account=self.account)

        in_collection = False
        if trakt_data.id in cache:
            series = cache[trakt_data.id]
            # specials are not included
            number_of_collected_episodes = sum(
                len(s['episodes']) for s in series['seasons'] if s['number'] > 0
            )
            in_collection = number_of_collected_episodes >= trakt_data.aired_episodes

        logger.debug(
            'The result for show entry "{}" is: {}',
            title,
            'Owned' if in_collection else 'Not owned',
        )
        return in_collection

    def is_season_in_collection(self, trakt_data, title):
        cache = user_cache.get_shows_collection(
            username=db.get_username(self.username, self.account), account=self.account
        )

        in_collection = False
        if trakt_data.show.id in cache:
            series = cache[trakt_data.show.id]
            for s in series['seasons']:
                if trakt_data.number == s['number']:
                    in_collection = True
                    break

        logger.debug(
            'The result for season entry "{}" is: {}',
            title,
            'Owned' if in_collection else 'Not owned',
        )
        return in_collection

    def is_episode_in_collection(self, trakt_data, title):
        cache = user_cache.get_shows_collection(self.username, self.account)

        in_collection = False
        if trakt_data.show.id in cache:
            series = cache[trakt_data.show.id]
            for s in series['seasons']:
                if s['number'] == trakt_data.season:
                    # extract all episode numbers currently in collection for the season number
                    episodes = [ep['number'] for ep in s['episodes']]
                    in_collection = trakt_data.number in episodes
                    break

        logger.debug(
            'The result for episode entry "{}" is: {}',
            title,
            'Owned' if in_collection else 'Not owned',
        )
        return in_collection

    def is_movie_in_collection(self, trakt_data, title):
        cache = user_cache.get_movie_collection(self.username, self.account)
        in_collection = trakt_data.id in cache
        logger.debug(
            'The result for movie entry "{}" is: {}',
            title,
            'Owned' if in_collection else 'Not owned',
        )
        return in_collection

    def is_show_watched(self, trakt_data, title):
        cache = user_cache.get_watched_shows(username=self.username, account=self.account)
        is_watched = False
        if trakt_data.id in cache:
            series = cache[trakt_data.id]
            # specials are not included
            number_of_watched_episodes = sum(
                len(s['episodes']) for s in series['seasons'] if s['number'] > 0
            )
            is_watched = number_of_watched_episodes == trakt_data.aired_episodes

        logger.debug(
            'The result for show entry "{}" is: {}',
            title,
            'Watched' if is_watched else 'Not watched',
        )
        return is_watched

    def is_season_watched(self, trakt_data, title):
        cache = user_cache.get_watched_shows(username=self.username, account=self.account)

        is_watched = False
        if trakt_data.show.id in cache:
            series = cache[trakt_data.show.id]
            for s in series['seasons']:
                if trakt_data.number == s['number']:
                    is_watched = True
                    break
        logger.debug(
            'The result for season entry "{}" is: {}',
            title,
            'Watched' if is_watched else 'Not watched',
        )
        return is_watched

    def is_episode_watched(self, trakt_data, title):
        cache = user_cache.get_watched_shows(username=self.username, account=self.account)
        is_watched = False
        if trakt_data.show.id in cache:
            series = cache[trakt_data.show.id]
            for s in series['seasons']:
                if s['number'] == trakt_data.season:
                    # extract all episode numbers currently in collection for the season number
                    episodes = [ep['number'] for ep in s['episodes']]
                    is_watched = trakt_data.number in episodes
                    break
        logger.debug(
            'The result for episode entry "{}" is: {}',
            title,
            'Watched' if is_watched else 'Not watched',
        )
        return is_watched

    def is_movie_watched(self, trakt_data, title):
        cache = user_cache.get_watched_movies(username=self.username, account=self.account)
        is_watched = trakt_data.id in cache
        logger.debug(
            'The result for movie entry "{}" is: {}',
            title,
            'Watched' if is_watched else 'Not watched',
        )
        return is_watched

    def show_user_ratings(self, trakt_data, title):
        cache = user_cache.get_show_user_ratings(username=self.username, account=self.account)
        user_rating = None
        if trakt_data.id in cache:
            user_rating = cache[trakt_data.id]['rating']
        logger.debug('User rating for show entry "{}" is: {}', title, user_rating)
        return user_rating

    def season_user_ratings(self, trakt_data, title):
        cache = user_cache.get_season_user_ratings(username=self.username, account=self.account)
        user_rating = None
        if trakt_data.id in cache and trakt_data.number == cache[trakt_data.id]['number']:
            user_rating = cache[trakt_data.id]['rating']
        logger.debug('User rating for season entry "{}" is: {}', title, user_rating)
        return user_rating

    def episode_user_ratings(self, trakt_data, title):
        cache = user_cache.get_episode_user_ratings(username=self.username, account=self.account)
        user_rating = None
        if trakt_data.id in cache:
            user_rating = cache[trakt_data.id]['rating']
        logger.debug('User rating for episode entry "{}" is: {}', title, user_rating)
        return user_rating

    def movie_user_ratings(self, trakt_data, title):
        cache = user_cache.get_movie_user_ratings(username=self.username, account=self.account)
        user_rating = None
        if trakt_data.id in cache:
            user_rating = cache[trakt_data.id]['rating']
        logger.debug('User rating for movie entry "{}" is: {}', title, user_rating)
        return user_rating


@event('plugin.register')
def register_plugin():
    plugin.register(ApiTrakt, 'api_trakt', api_ver=2, interfaces=[])
