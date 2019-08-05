# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, absolute_import, print_function
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
import time

from datetime import datetime, timedelta
from dateutil.parser import parse as dateutil_parse
from sqlalchemy import Table, Column, Integer, String, Unicode, Date, DateTime, Time, or_, and_
from sqlalchemy.orm import relation
from sqlalchemy.schema import ForeignKey

from flexget import db_schema
from flexget import plugin
from flexget.terminal import console
from flexget.manager import Session
from flexget.utils import requests
from flexget.utils.database import json_synonym
from flexget.utils.tools import split_title_year

Base = db_schema.versioned_base('api_trakt', 7)
AuthBase = db_schema.versioned_base('trakt_auth', 0)
log = logging.getLogger('api_trakt')
# Production Site
CLIENT_ID = '57e188bcb9750c79ed452e1674925bc6848bd126e02bb15350211be74c6547af'
CLIENT_SECRET = 'db4af7531e8df678b134dbc22445a2c04ebdbdd7213be7f5b6d17dfdfabfcdc2'
API_URL = 'https://api.trakt.tv/'
PIN_URL = 'https://trakt.tv/pin/346'


# Oauth account authentication
class TraktUserAuth(AuthBase):
    __tablename__ = 'trakt_user_auth'

    account = Column(Unicode, primary_key=True)
    access_token = Column(Unicode)
    refresh_token = Column(Unicode)
    created = Column(DateTime)
    expires = Column(DateTime)

    def __init__(self, account, access_token, refresh_token, created, expires):
        self.account = account
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires = token_expire_date(expires)
        self.created = token_created_date(created)


def token_expire_date(expires):
    return datetime.now() + timedelta(seconds=expires)


def token_created_date(created):
    return datetime.fromtimestamp(created)


def device_auth():
    data = {'client_id': CLIENT_ID}
    try:
        r = requests.post(get_api_url('oauth/device/code'), data=data).json()
        device_code = r['device_code']
        user_code = r['user_code']
        expires_in = r['expires_in']
        interval = r['interval']

        console(
            'Please visit {0} and authorize Flexget. Your user code is {1}. Your code expires in '
            '{2} minutes.'.format(r['verification_url'], user_code, expires_in / 60.0)
        )

        log.debug('Polling for user authorization.')
        data['code'] = device_code
        data['client_secret'] = CLIENT_SECRET
        end_time = time.time() + expires_in
        console('Waiting...', end='')
        # stop polling after expires_in seconds
        while time.time() < end_time:
            time.sleep(interval)
            polling_request = requests.post(
                get_api_url('oauth/device/token'), data=data, raise_status=False
            )
            if polling_request.status_code == 200:  # success
                return polling_request.json()
            elif polling_request.status_code == 400:  # pending -- waiting for user
                console('...', end='')
            elif polling_request.status_code == 404:  # not found -- invalid device_code
                raise plugin.PluginError('Invalid device code. Open an issue on Github.')
            elif polling_request.status_code == 409:  # already used -- user already approved
                raise plugin.PluginError('User code has already been approved.')
            elif polling_request.status_code == 410:  # expired -- restart process
                break
            elif polling_request.status_code == 418:  # denied -- user denied code
                raise plugin.PluginError('User code has been denied.')
            elif polling_request.status_code == 429:  # polling too fast
                log.warning('Polling too quickly. Upping the interval. No action required.')
                interval += 1
        raise plugin.PluginError('User code has expired. Please try again.')
    except requests.RequestException as e:
        raise plugin.PluginError('Device authorization with Trakt.tv failed: {0}'.format(e))


def token_oauth(data):
    try:
        return requests.post(get_api_url('oauth/token'), data=data).json()
    except requests.RequestException as e:
        raise plugin.PluginError('Token exchange with trakt failed: {0}'.format(e))


def delete_account(account):
    with Session() as session:
        acc = session.query(TraktUserAuth).filter(TraktUserAuth.account == account).first()
        if not acc:
            raise plugin.PluginError('Account %s not found.' % account)
        session.delete(acc)


def get_access_token(account, token=None, refresh=False, re_auth=False, called_from_cli=False):
    """
    Gets authorization info from a pin or refresh token.
    :param account: Arbitrary account name to attach authorization to.
    :param unicode token: The pin or refresh token, as supplied by the trakt website.
    :param bool refresh: If True, refresh the access token using refresh_token from db.
    :param bool re_auth: If True, account is re-authorized even if it already exists in db.
    :raises RequestException: If there is a network error while authorizing.
    """
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob',
    }
    with Session() as session:
        acc = session.query(TraktUserAuth).filter(TraktUserAuth.account == account).first()
        if acc and datetime.now() < acc.expires and not refresh and not re_auth:
            return acc.access_token
        else:
            if (
                acc
                and (refresh or datetime.now() >= acc.expires - timedelta(days=5))
                and not re_auth
            ):
                log.debug('Using refresh token to re-authorize account %s.', account)
                data['refresh_token'] = acc.refresh_token
                data['grant_type'] = 'refresh_token'
                token_dict = token_oauth(data)
            elif token:
                # We are only in here if a pin was specified, so it's safe to use console instead of logging
                console(
                    'Warning: PIN authorization has been deprecated. Use Device Authorization instead.'
                )
                data['code'] = token
                data['grant_type'] = 'authorization_code'
                token_dict = token_oauth(data)
            elif called_from_cli:
                log.debug(
                    'No pin specified for an unknown account %s. Attempting to authorize device.',
                    account,
                )
                token_dict = device_auth()
            else:
                raise plugin.PluginError(
                    'Account %s has not been authorized. See `flexget trakt auth -h` on how to.'
                    % account
                )
            try:
                new_acc = TraktUserAuth(
                    account,
                    token_dict['access_token'],
                    token_dict['refresh_token'],
                    token_dict.get('created_at', time.time()),
                    token_dict['expires_in'],
                )
                session.merge(new_acc)
                return new_acc.access_token
            except requests.RequestException as e:
                raise plugin.PluginError('Token exchange with trakt failed: {0}'.format(e))


def make_list_slug(name):
    """Return the slug for use in url for given list name."""
    slug = name.lower()
    # These characters are just stripped in the url
    for char in '!@#$%^*()[]{}/=?+\\|':
        slug = slug.replace(char, '')
    # These characters get replaced
    slug = slug.replace('&', 'and')
    slug = slug.replace(' ', '-')
    return slug


def get_session(account=None, token=None):
    """
    Creates a requests session ready to talk to trakt API with FlexGet's api key.
    Can also add user level authentication if `account` parameter is given.
    :param account: An account authorized via `flexget trakt auth` CLI command. If given, returned session will be
        authenticated for that account.
    """
    # default to username if account name is not specified
    session = requests.Session()
    session.headers = {
        'Content-Type': 'application/json',
        'trakt-api-version': '2',
        'trakt-api-key': CLIENT_ID,
    }
    if account:
        access_token = get_access_token(account, token) if account else None
        if access_token:
            session.headers.update({'Authorization': 'Bearer %s' % access_token})
    return session


def get_api_url(*endpoint):
    """
    Get the address of a trakt API endpoint.
    :param endpoint: Can by a string endpoint (e.g. 'sync/watchlist') or an iterable (e.g. ('sync', 'watchlist')
        Multiple parameters can also be specified instead of a single iterable.
    :returns: The absolute url to the specified API endpoint.
    """
    if len(endpoint) == 1 and not isinstance(endpoint[0], str):
        endpoint = endpoint[0]
    # Make sure integer portions are turned into strings first too
    url = API_URL + '/'.join(map(str, endpoint))
    return url


@db_schema.upgrade('api_trakt')
def upgrade(ver, session):
    if ver is None or ver <= 6:
        raise db_schema.UpgradeImpossible
    return ver


def get_entry_ids(entry):
    """Creates a trakt ids dict from id fields on an entry. Prefers already populated info over lazy lookups."""
    ids = {}
    for lazy in [False, True]:
        if entry.get('trakt_movie_id', eval_lazy=lazy):
            ids['trakt'] = entry['trakt_movie_id']
        elif entry.get('trakt_show_id', eval_lazy=lazy):
            ids['trakt'] = entry['trakt_show_id']
        elif entry.get('trakt_episode_id', eval_lazy=lazy):
            ids['trakt'] = entry['trakt_episode_id']
        if entry.get('tmdb_id', eval_lazy=lazy):
            ids['tmdb'] = entry['tmdb_id']
        if entry.get('tvdb_id', eval_lazy=lazy):
            ids['tvdb'] = entry['tvdb_id']
        if entry.get('imdb_id', eval_lazy=lazy):
            ids['imdb'] = entry['imdb_id']
        if entry.get('tvrage_id', eval_lazy=lazy):
            ids['tvrage'] = entry['tvrage_id']
        if ids:
            break
    return ids


class TraktMovieTranslation(Base):
    __tablename__ = 'trakt_movie_translations'

    id = Column(Integer, primary_key=True, autoincrement=True)
    language = Column(Unicode)
    overview = Column(Unicode)
    tagline = Column(Unicode)
    title = Column(Unicode)
    movie_id = Column(Integer, ForeignKey('trakt_movies.id'))

    def __init__(self, translation, session):
        super(TraktMovieTranslation, self).__init__()
        self.update(translation, session)

    def update(self, translation, session):
        for col in translation.keys():
            setattr(self, col, translation.get(col))


class TraktShowTranslation(Base):
    __tablename__ = 'trakt_show_translations'

    id = Column(Integer, primary_key=True, autoincrement=True)
    language = Column(Unicode)
    overview = Column(Unicode)
    title = Column(Unicode)
    show_id = Column(Integer, ForeignKey('trakt_shows.id'))

    def __init__(self, translation, session):
        super(TraktShowTranslation, self).__init__()
        self.update(translation, session)

    def update(self, translation, session):
        for col in translation.keys():
            setattr(self, col, translation.get(col))


def get_translations(ident, style):
    url = get_api_url(style + 's', ident, 'translations')
    trakt_translation = TraktShowTranslation if style == 'show' else TraktMovieTranslation
    trakt_translation_id = getattr(trakt_translation, style + '_id')
    translations = []
    req_session = get_session()
    try:
        results = req_session.get(url, params={'extended': 'full'}).json()
        with Session() as session:
            for result in results:
                translation = (
                    session.query(trakt_translation)
                    .filter(
                        and_(
                            trakt_translation.language == result.get('language'),
                            trakt_translation_id == ident,
                        )
                    )
                    .first()
                )
                if not translation:
                    translation = trakt_translation(result, session)
                translations.append(translation)
        return translations
    except requests.RequestException as e:
        log.debug('Error adding translations to trakt id %s: %s', ident, e)


class TraktGenre(Base):
    __tablename__ = 'trakt_genres'

    name = Column(Unicode, primary_key=True)


show_genres_table = Table(
    'trakt_show_genres',
    Base.metadata,
    Column('show_id', Integer, ForeignKey('trakt_shows.id')),
    Column('genre_id', Unicode, ForeignKey('trakt_genres.name')),
)
Base.register_table(show_genres_table)

movie_genres_table = Table(
    'trakt_movie_genres',
    Base.metadata,
    Column('movie_id', Integer, ForeignKey('trakt_movies.id')),
    Column('genre_id', Unicode, ForeignKey('trakt_genres.name')),
)
Base.register_table(movie_genres_table)


class TraktActor(Base):
    __tablename__ = 'trakt_actors'

    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(Unicode)
    slug = Column(Unicode)
    tmdb = Column(Integer)
    imdb = Column(Unicode)
    biography = Column(Unicode)
    birthday = Column(Date)
    death = Column(Date)
    homepage = Column(Unicode)

    def __init__(self, actor, session):
        super(TraktActor, self).__init__()
        self.update(actor, session)

    def update(self, actor, session):
        if self.id and self.id != actor.get('ids').get('trakt'):
            raise Exception('Tried to update db actors with different actor data')
        elif not self.id:
            self.id = actor.get('ids').get('trakt')
        self.name = actor.get('name')
        ids = actor.get('ids')
        self.imdb = ids.get('imdb')
        self.slug = ids.get('slug')
        self.tmdb = ids.get('tmdb')
        self.biography = actor.get('biography')
        if actor.get('birthday'):
            self.birthday = dateutil_parse(actor.get('birthday'))
        if actor.get('death'):
            self.death = dateutil_parse(actor.get('death'))
        self.homepage = actor.get('homepage')

    def to_dict(self):
        return {'name': self.name, 'trakt_id': self.id, 'imdb_id': self.imdb, 'tmdb_id': self.tmdb}


show_actors_table = Table(
    'trakt_show_actors',
    Base.metadata,
    Column('show_id', Integer, ForeignKey('trakt_shows.id')),
    Column('actors_id', Integer, ForeignKey('trakt_actors.id')),
)
Base.register_table(show_actors_table)

movie_actors_table = Table(
    'trakt_movie_actors',
    Base.metadata,
    Column('movie_id', Integer, ForeignKey('trakt_movies.id')),
    Column('actors_id', Integer, ForeignKey('trakt_actors.id')),
)
Base.register_table(movie_actors_table)


def get_db_actors(ident, style):
    actors = {}
    url = get_api_url(style + 's', ident, 'people')
    req_session = get_session()
    try:
        results = req_session.get(url, params={'extended': 'full'}).json()
        with Session() as session:
            for result in results.get('cast'):
                trakt_id = result.get('person').get('ids').get('trakt')
                # sometimes an actor can occur twice in the list by mistake. This check is to avoid this unlikely event
                if trakt_id in actors:
                    continue
                actor = session.query(TraktActor).filter(TraktActor.id == trakt_id).first()
                if not actor:
                    actor = TraktActor(result.get('person'), session)
                actors[trakt_id] = actor
        return list(actors.values())
    except requests.RequestException as e:
        log.debug('Error searching for actors for trakt id %s', e)
        return


def get_translations_dict(translate, style):
    res = {}
    for lang in translate:
        info = {'overview': lang.overview, 'title': lang.title}
        if style == 'movie':
            info['tagline'] = lang.tagline
        res[lang.language] = info
    return res


def list_actors(actors):
    res = {}
    for actor in actors:
        info = {
            'trakt_id': actor.id,
            'name': actor.name,
            'imdb_id': str(actor.imdb),
            'trakt_slug': actor.slug,
            'tmdb_id': str(actor.tmdb),
            'birthday': actor.birthday.strftime("%Y/%m/%d") if actor.birthday else None,
            'biography': actor.biography,
            'homepage': actor.homepage,
            'death': actor.death.strftime("%Y/%m/%d") if actor.death else None,
        }
        res[str(actor.id)] = info
    return res


class TraktEpisode(Base):
    __tablename__ = 'trakt_episodes'

    id = Column(Integer, primary_key=True, autoincrement=False)
    tvdb_id = Column(Integer)
    imdb_id = Column(Unicode)
    tmdb_id = Column(Integer)
    tvrage_id = Column(Unicode)
    title = Column(Unicode)
    season = Column(Integer)
    number = Column(Integer)
    number_abs = Column(Integer)
    overview = Column(Unicode)
    first_aired = Column(DateTime)
    updated_at = Column(DateTime)
    cached_at = Column(DateTime)

    series_id = Column(Integer, ForeignKey('trakt_shows.id'), nullable=False)

    def __init__(self, trakt_episode, session):
        super(TraktEpisode, self).__init__()
        self.update(trakt_episode, session)

    def update(self, trakt_episode, session):
        """Updates this record from the trakt media object `trakt_episode` returned by the trakt api."""
        if self.id and self.id != trakt_episode['ids']['trakt']:
            raise Exception('Tried to update db ep with different ep data')
        elif not self.id:
            self.id = trakt_episode['ids']['trakt']
        self.imdb_id = trakt_episode['ids']['imdb']
        self.tmdb_id = trakt_episode['ids']['tmdb']
        self.tvrage_id = trakt_episode['ids']['tvrage']
        self.tvdb_id = trakt_episode['ids']['tvdb']
        self.first_aired = None
        if trakt_episode.get('first_aired'):
            self.first_aired = dateutil_parse(trakt_episode['first_aired'], ignoretz=True)
        self.updated_at = dateutil_parse(trakt_episode.get('updated_at'), ignoretz=True)
        self.cached_at = datetime.now()

        for col in ['title', 'season', 'number', 'number_abs', 'overview']:
            setattr(self, col, trakt_episode.get(col))

    @property
    def expired(self):
        # TODO should episode have its own expiration function?
        return False


class TraktSeason(Base):
    __tablename__ = 'trakt_seasons'

    id = Column(Integer, primary_key=True, autoincrement=False)
    tvdb_id = Column(Integer)
    tmdb_id = Column(Integer)
    tvrage_id = Column(Unicode)
    title = Column(Unicode)
    number = Column(Integer)
    episode_count = Column(Integer)
    aired_episodes = Column(Integer)
    overview = Column(Unicode)
    first_aired = Column(DateTime)
    ratings = Column(Integer)
    votes = Column(Integer)

    cached_at = Column(DateTime)

    series_id = Column(Integer, ForeignKey('trakt_shows.id'), nullable=False)

    def __init__(self, trakt_season, session):
        super(TraktSeason, self).__init__()
        self.update(trakt_season, session)

    def update(self, trakt_season, session):
        """Updates this record from the trakt media object `trakt_episode` returned by the trakt api."""
        if self.id and self.id != trakt_season['ids']['trakt']:
            raise Exception('Tried to update db season with different season data')
        elif not self.id:
            self.id = trakt_season['ids']['trakt']
        self.tmdb_id = trakt_season['ids']['tmdb']
        self.tvrage_id = trakt_season['ids']['tvrage']
        self.tvdb_id = trakt_season['ids']['tvdb']
        self.first_aired = None
        if trakt_season.get('first_aired'):
            self.first_aired = dateutil_parse(trakt_season['first_aired'], ignoretz=True)
        self.cached_at = datetime.now()

        for col in [
            'title',
            'number',
            'episode_count',
            'aired_episodes',
            'ratings',
            'votes',
            'overview',
        ]:
            setattr(self, col, trakt_season.get(col))

    @property
    def expired(self):
        # TODO should season have its own expiration function?
        return False


class TraktShow(Base):
    __tablename__ = 'trakt_shows'

    id = Column(Integer, primary_key=True, autoincrement=False)
    title = Column(Unicode)
    year = Column(Integer)
    slug = Column(Unicode)
    tvdb_id = Column(Integer)
    imdb_id = Column(Unicode)
    tmdb_id = Column(Integer)
    tvrage_id = Column(Unicode)
    overview = Column(Unicode)
    first_aired = Column(DateTime)
    air_day = Column(Unicode)
    air_time = Column(Time)
    timezone = Column(Unicode)
    runtime = Column(Integer)
    certification = Column(Unicode)
    network = Column(Unicode)
    country = Column(Unicode)
    status = Column(String)
    rating = Column(Integer)
    votes = Column(Integer)
    language = Column(Unicode)
    homepage = Column(Unicode)
    trailer = Column(Unicode)
    aired_episodes = Column(Integer)
    _translations = relation(TraktShowTranslation)
    _translation_languages = Column('translation_languages', Unicode)
    translation_languages = json_synonym('_translation_languages')
    episodes = relation(
        TraktEpisode, backref='show', cascade='all, delete, delete-orphan', lazy='dynamic'
    )
    seasons = relation(
        TraktSeason, backref='show', cascade='all, delete, delete-orphan', lazy='dynamic'
    )
    genres = relation(TraktGenre, secondary=show_genres_table)
    _actors = relation(TraktActor, secondary=show_actors_table)
    updated_at = Column(DateTime)
    cached_at = Column(DateTime)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "year": self.year,
            "slug": self.slug,
            "tvdb_id": self.tvdb_id,
            "imdb_id": self.imdb_id,
            "tmdb_id": self.tmdb_id,
            "tvrage_id": self.tvrage_id,
            "overview": self.overview,
            "first_aired": self.first_aired,
            "air_day": self.air_day,
            "air_time": self.air_time.strftime("%H:%M") if self.air_time else None,
            "timezone": self.timezone,
            "runtime": self.runtime,
            "certification": self.certification,
            "network": self.network,
            "country": self.country,
            "status": self.status,
            "rating": self.rating,
            "votes": self.votes,
            "language": self.language,
            "homepage": self.homepage,
            "number_of_aired_episodes": self.aired_episodes,
            "genres": [g.name for g in self.genres],
            "updated_at": self.updated_at,
            "cached_at": self.cached_at,
        }

    def __init__(self, trakt_show, session):
        super(TraktShow, self).__init__()
        self.update(trakt_show, session)

    def update(self, trakt_show, session):
        """Updates this record from the trakt media object `trakt_show` returned by the trakt api."""
        if self.id and self.id != trakt_show['ids']['trakt']:
            raise Exception('Tried to update db show with different show data')
        elif not self.id:
            self.id = trakt_show['ids']['trakt']
        self.slug = trakt_show['ids']['slug']
        self.imdb_id = trakt_show['ids']['imdb']
        self.tmdb_id = trakt_show['ids']['tmdb']
        self.tvrage_id = trakt_show['ids']['tvrage']
        self.tvdb_id = trakt_show['ids']['tvdb']
        if trakt_show.get('airs'):
            airs = trakt_show.get('airs')
            self.air_day = airs.get('day')
            self.timezone = airs.get('timezone')
            if airs.get('time'):
                self.air_time = datetime.strptime(airs.get('time'), '%H:%M').time()
            else:
                self.air_time = None
        if trakt_show.get('first_aired'):
            self.first_aired = dateutil_parse(trakt_show.get('first_aired'), ignoretz=True)
        else:
            self.first_aired = None
        self.updated_at = dateutil_parse(trakt_show.get('updated_at'), ignoretz=True)

        for col in [
            'overview',
            'runtime',
            'rating',
            'votes',
            'language',
            'title',
            'year',
            'runtime',
            'certification',
            'network',
            'country',
            'status',
            'aired_episodes',
            'trailer',
            'homepage',
        ]:
            setattr(self, col, trakt_show.get(col))

        # Sometimes genres and translations are None but we really do want a list, hence the "or []"
        self.genres = [
            TraktGenre(name=g.replace(' ', '-')) for g in trakt_show.get('genres') or []
        ]
        self.cached_at = datetime.now()
        self.translation_languages = trakt_show.get('available_translations') or []

    def get_episode(self, season, number, session, only_cached=False):
        # TODO: Does series data being expired mean all episode data should be refreshed?
        episode = (
            self.episodes.filter(TraktEpisode.season == season)
            .filter(TraktEpisode.number == number)
            .first()
        )
        if not episode or self.expired:
            url = get_api_url(
                'shows', self.id, 'seasons', season, 'episodes', number, '?extended=full'
            )
            if only_cached:
                raise LookupError('Episode %s %s not found in cache' % (season, number))
            log.debug('Episode %s %s not found in cache, looking up from trakt.', season, number)
            try:
                data = get_session().get(url).json()
            except requests.RequestException:
                raise LookupError('Error Retrieving Trakt url: %s' % url)
            if not data:
                raise LookupError('No data in response from trakt %s' % url)
            episode = self.episodes.filter(TraktEpisode.id == data['ids']['trakt']).first()
            if episode:
                episode.update(data, session)
            else:
                episode = TraktEpisode(data, session)
                self.episodes.append(episode)
            session.commit()
        return episode

    def get_season(self, number, session, only_cached=False):
        # TODO: Does series data being expired mean all season data should be refreshed?
        season = self.seasons.filter(TraktSeason.number == number).first()
        if not season or self.expired:
            url = get_api_url('shows', self.id, 'seasons', '?extended=full')
            if only_cached:
                raise LookupError('Season %s not found in cache' % number)
            log.debug('Season %s not found in cache, looking up from trakt.', number)
            try:
                ses = get_session()
                data = ses.get(url).json()
            except requests.RequestException:
                raise LookupError('Error Retrieving Trakt url: %s' % url)
            if not data:
                raise LookupError('No data in response from trakt %s' % url)
            # We fetch all seasons for the given show because we barely get any data otherwise
            for season_result in data:
                db_season = self.seasons.filter(
                    TraktSeason.id == season_result['ids']['trakt']
                ).first()
                if db_season:
                    db_season.update(season_result, session)
                else:
                    db_season = TraktSeason(season_result, session)
                    self.seasons.append(db_season)
                if number == season_result['number']:
                    season = db_season
            if not season:
                raise LookupError('Season %s not found for show %s' % (number, self.title))
            session.commit()
        return season

    @property
    def expired(self):
        """
        :return: True if show details are considered to be expired, ie. need of update
        """
        # TODO stolen from imdb plugin, maybe there's a better way?
        if self.cached_at is None:
            log.debug('cached_at is None: %s', self)
            return True
        refresh_interval = 2
        # if show has been cancelled or ended, then it is unlikely to be updated often
        if self.year and (self.status == 'ended' or self.status == 'canceled'):
            # Make sure age is not negative
            age = max((datetime.now().year - self.year), 0)
            refresh_interval += age * 5
            log.debug('show `%s` age %i expires in %i days', self.title, age, refresh_interval)
        return self.cached_at < datetime.now() - timedelta(days=refresh_interval)

    @property
    def translations(self):
        if not self._translations:
            self._translations = get_translations(self.id, 'show')
        return self._translations

    @property
    def actors(self):
        if not self._actors:
            self._actors[:] = get_db_actors(self.id, 'show')
        return self._actors

    def __repr__(self):
        return '<name=%s, id=%s>' % (self.title, self.id)


class TraktMovie(Base):
    __tablename__ = 'trakt_movies'

    id = Column(Integer, primary_key=True, autoincrement=False)
    title = Column(Unicode)
    year = Column(Integer)
    slug = Column(Unicode)
    imdb_id = Column(Unicode)
    tmdb_id = Column(Integer)
    tagline = Column(Unicode)
    overview = Column(Unicode)
    released = Column(Date)
    runtime = Column(Integer)
    rating = Column(Integer)
    votes = Column(Integer)
    trailer = Column(Unicode)
    homepage = Column(Unicode)
    language = Column(Unicode)
    updated_at = Column(DateTime)
    cached_at = Column(DateTime)
    _translations = relation(TraktMovieTranslation, backref='movie')
    _translation_languages = Column('translation_languages', Unicode)
    translation_languages = json_synonym('_translation_languages')
    genres = relation(TraktGenre, secondary=movie_genres_table)
    _actors = relation(TraktActor, secondary=movie_actors_table)

    def __init__(self, trakt_movie, session):
        super(TraktMovie, self).__init__()
        self.update(trakt_movie, session)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "year": self.year,
            "slug": self.slug,
            "imdb_id": self.imdb_id,
            "tmdb_id": self.tmdb_id,
            "tagline": self.tagline,
            "overview": self.overview,
            "released": self.released,
            "runtime": self.runtime,
            "rating": self.rating,
            "votes": self.votes,
            "language": self.language,
            "homepage": self.homepage,
            "trailer": self.trailer,
            "genres": [g.name for g in self.genres],
            "updated_at": self.updated_at,
            "cached_at": self.cached_at,
        }

    def update(self, trakt_movie, session):
        """Updates this record from the trakt media object `trakt_movie` returned by the trakt api."""
        if self.id and self.id != trakt_movie['ids']['trakt']:
            raise Exception('Tried to update db movie with different movie data')
        elif not self.id:
            self.id = trakt_movie['ids']['trakt']
        self.slug = trakt_movie['ids']['slug']
        self.imdb_id = trakt_movie['ids']['imdb']
        self.tmdb_id = trakt_movie['ids']['tmdb']
        for col in [
            'title',
            'overview',
            'runtime',
            'rating',
            'votes',
            'language',
            'tagline',
            'year',
            'trailer',
            'homepage',
        ]:
            setattr(self, col, trakt_movie.get(col))
        if trakt_movie.get('released'):
            self.released = dateutil_parse(trakt_movie.get('released'), ignoretz=True).date()
        self.updated_at = dateutil_parse(trakt_movie.get('updated_at'), ignoretz=True)
        self.genres = [TraktGenre(name=g.replace(' ', '-')) for g in trakt_movie.get('genres', [])]
        self.cached_at = datetime.now()
        self.translation_languages = trakt_movie.get('available_translations', [])

    @property
    def expired(self):
        """
        :return: True if movie details are considered to be expired, ie. need of update
        """
        # TODO stolen from imdb plugin, maybe there's a better way?
        if self.updated_at is None:
            log.debug('updated_at is None: %s', self)
            return True
        refresh_interval = 2
        if self.year:
            # Make sure age is not negative
            age = max((datetime.now().year - self.year), 0)
            refresh_interval += age * 5
            log.debug('movie `%s` age %i expires in %i days', self.title, age, refresh_interval)
        return self.cached_at < datetime.now() - timedelta(days=refresh_interval)

    @property
    def translations(self):
        if not self._translations:
            self._translations = get_translations(self.id, 'movie')
        return self._translations

    @property
    def actors(self):
        if not self._actors:
            self._actors[:] = get_db_actors(self.id, 'movie')
        return self._actors


class TraktShowSearchResult(Base):
    __tablename__ = 'trakt_show_search_results'

    id = Column(Integer, primary_key=True)
    search = Column(Unicode, unique=True, nullable=False)
    series_id = Column(Integer, ForeignKey('trakt_shows.id'), nullable=True)
    series = relation(TraktShow, backref='search_strings')

    def __init__(self, search, series_id=None, series=None):
        self.search = search.lower()
        if series_id:
            self.series_id = series_id
        if series:
            self.series = series


class TraktMovieSearchResult(Base):
    __tablename__ = 'trakt_movie_search_results'

    id = Column(Integer, primary_key=True)
    search = Column(Unicode, unique=True, nullable=False)
    movie_id = Column(Integer, ForeignKey('trakt_movies.id'), nullable=True)
    movie = relation(TraktMovie, backref='search_strings')

    def __init__(self, search, movie_id=None, movie=None):
        self.search = search.lower()
        if movie_id:
            self.movie_id = movie_id
        if movie:
            self.movie = movie


class TraktMovieIds(object):
    """Simple class that holds a variety of possible IDs that Trakt utilize in their API, eg. imdb id, trakt id"""

    def __init__(self, trakt_id=None, trakt_slug=None, tmdb_id=None, imdb_id=None, **kwargs):
        self.trakt_id = trakt_id
        self.trakt_slug = trakt_slug
        self.tmdb_id = tmdb_id
        self.imdb_id = imdb_id

    def get_trakt_id(self):
        return self.trakt_id or self.trakt_slug

    def to_dict(self):
        """Returns a dict containing id fields that are relevant for a movie"""
        return {
            'id': self.trakt_id,
            'slug': self.trakt_slug,
            'tmdb_id': self.tmdb_id,
            'imdb_id': self.imdb_id,
        }

    def __bool__(self):
        return any([self.trakt_id, self.trakt_slug, self.tmdb_id, self.imdb_id])


class TraktShowIds(object):
    """Simple class that holds a variety of possible IDs that Trakt utilize in their API, eg. imdb id, trakt id"""

    def __init__(
        self,
        trakt_id=None,
        trakt_slug=None,
        tmdb_id=None,
        imdb_id=None,
        tvdb_id=None,
        tvrage_id=None,
        **kwargs
    ):
        self.trakt_id = trakt_id
        self.trakt_slug = trakt_slug
        self.tmdb_id = tmdb_id
        self.imdb_id = imdb_id
        self.tvdb_id = tvdb_id
        self.tvrage_id = tvrage_id

    def get_trakt_id(self):
        return self.trakt_id or self.trakt_slug

    def to_dict(self):
        """Returns a dict containing id fields that are relevant for a show/season/episode"""
        return {
            'id': self.trakt_id,
            'slug': self.trakt_slug,
            'tmdb_id': self.tmdb_id,
            'imdb_id': self.imdb_id,
            'tvdb_id': self.tvdb_id,
            'tvrage_id': self.tvrage_id,
        }

    def __bool__(self):
        return any(
            [
                self.trakt_id,
                self.trakt_slug,
                self.tmdb_id,
                self.imdb_id,
                self.tvdb_id,
                self.tvrage_id,
            ]
        )


def get_item_from_cache(table, session, title=None, year=None, trakt_ids=None):
    """
    Get the cached info for a given show/movie from the database.
    :param table: Either TraktMovie or TraktShow
    :param title: Title of the show/movie
    :param year: First release year
    :param trakt_ids: instance of TraktShowIds or TraktMovieIds
    :param session: database session object
    :return: query result
    """
    result = None
    if trakt_ids:
        result = (
            session.query(table)
            .filter(
                or_(getattr(table, col) == val for col, val in trakt_ids.to_dict().items() if val)
            )
            .first()
        )
    elif title:
        title, y = split_title_year(title)
        year = year or y
        query = session.query(table).filter(table.title == title)
        if year:
            query = query.filter(table.year == year)
        result = query.first()
    return result


def get_trakt_id_from_id(trakt_ids, media_type):
    if not trakt_ids:
        raise LookupError('No lookup arguments provided.')
    requests_session = get_session()
    for id_type, identifier in trakt_ids.to_dict().items():
        if not identifier:
            continue
        stripped_id_type = id_type.rstrip('_id')  # need to remove _id for the api call
        try:
            log.debug('Searching with params: %s=%s', stripped_id_type, identifier)
            results = requests_session.get(
                get_api_url('search'), params={'id_type': stripped_id_type, 'id': identifier}
            ).json()
        except requests.RequestException as e:
            raise LookupError(
                'Searching trakt for %s=%s failed with error: %s'
                % (stripped_id_type, identifier, e)
            )
        for result in results:
            if result['type'] != media_type:
                continue
            return result[media_type]['ids']['trakt']


def get_trakt_id_from_title(title, media_type, year=None):
    if not title:
        raise LookupError('No lookup arguments provided.')
    requests_session = get_session()
    # Try finding trakt id based on title and year
    parsed_title, y = split_title_year(title)
    y = year or y
    try:
        params = {'query': parsed_title, 'type': media_type, 'year': y}
        log.debug('Type of title: %s', type(parsed_title))
        log.debug(
            'Searching with params: %s',
            ', '.join('{}={}'.format(k, v) for (k, v) in params.items()),
        )
        results = requests_session.get(get_api_url('search'), params=params).json()
    except requests.RequestException as e:
        raise LookupError('Searching trakt for %s failed with error: %s' % (title, e))
    for result in results:
        if year and result[media_type]['year'] != year:
            continue
        if parsed_title.lower() == result[media_type]['title'].lower():
            return result[media_type]['ids']['trakt']
    # grab the first result if there is no exact match
    if results:
        return results[0][media_type]['ids']['trakt']


def get_trakt_data(media_type, title=None, year=None, trakt_ids=None):
    trakt_id = None
    if trakt_ids:
        trakt_id = trakt_ids.get_trakt_id()

    if not trakt_id and trakt_ids:
        trakt_id = get_trakt_id_from_id(trakt_ids, media_type)

    if not trakt_id and title:
        trakt_id = get_trakt_id_from_title(title, media_type, year=year)

    if not trakt_id:
        raise LookupError(
            'No results on Trakt.tv, title=%s, ids=%s.'
            % (title, trakt_ids.to_dict if trakt_ids else None)
        )

    # Get actual data from trakt
    try:
        return (
            get_session()
            .get(get_api_url(media_type + 's', trakt_id), params={'extended': 'full'})
            .json()
        )
    except requests.RequestException as e:
        raise LookupError('Error getting trakt data for id %s: %s' % (trakt_id, e))


def get_user_data(data_type, media_type, session, username):
    """
    Fetches user data from Trakt.tv on the /users/<username>/<data_type>/<media_type> end point. Eg. a user's
    movie collection is fetched from /users/<username>/collection/movies.
    :param data_type: Name of the data type eg. collection, watched etc.
    :param media_type: Type of media we want <data_type> for eg. shows, episodes, movies.
    :param session: A trakt requests session with a valid token
    :param username: Username of the user to fetch data
    :return:
    """

    endpoint = '{}/{}'.format(data_type, media_type)
    try:
        data = session.get(get_api_url('users', username, data_type, media_type)).json()
        if not data:
            log.warning('No %s data returned from trakt endpoint %s.', data_type, endpoint)
            return []
        log.verbose(
            'Received %d records from trakt.tv for user %s from endpoint %s',
            len(data),
            username,
            endpoint,
        )

        # extract show, episode and movie information
        for item in data:
            episode = item.pop('episode', {})
            season = item.pop('season', {})
            show = item.pop('show', {})
            movie = item.pop('movie', {})
            item.update(episode)
            item.update(season)
            item.update(movie)
            # show is irrelevant if either episode or season is present
            if not episode and not season:
                item.update(show)

        return data

    except requests.RequestException as e:
        raise plugin.PluginError(
            'Error fetching data from trakt.tv endpoint %s for user %s: %s'
            % (endpoint, username, e)
        )


def get_username(username=None, account=None):
    """Returns 'me' if account is provided and username is not"""
    if not username and account:
        return 'me'
    return username
