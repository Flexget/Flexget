# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, absolute_import, print_function
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from past.builtins import basestring

import logging
import re
import time

from datetime import datetime, timedelta
from dateutil.parser import parse as dateutil_parse
from sqlalchemy import Table, Column, Integer, String, Unicode, Date, DateTime, Time, or_, and_
from sqlalchemy.orm import relation
from sqlalchemy.schema import ForeignKey

from flexget import db_schema
from flexget import plugin
from flexget.event import event
from flexget.terminal import console
from flexget.manager import Session
from flexget.plugin import get_plugin_by_name
from flexget.utils import requests
from flexget.utils.database import with_session, json_synonym
from flexget.utils.simple_persistence import SimplePersistence
from flexget.utils.tools import TimedDict

Base = db_schema.versioned_base('api_trakt', 7)
AuthBase = db_schema.versioned_base('trakt_auth', 0)
log = logging.getLogger('api_trakt')
# Production Site
CLIENT_ID = '57e188bcb9750c79ed452e1674925bc6848bd126e02bb15350211be74c6547af'
CLIENT_SECRET = 'db4af7531e8df678b134dbc22445a2c04ebdbdd7213be7f5b6d17dfdfabfcdc2'
API_URL = 'https://api.trakt.tv/'
PIN_URL = 'https://trakt.tv/pin/346'
# Stores the last time we checked for updates for shows/movies
updated = SimplePersistence('api_trakt')


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

        console('Please visit {0} and authorize Flexget. Your user code is {1}. Your code expires in '
                '{2} minutes.'.format(r['verification_url'], user_code, expires_in / 60.0))

        log.debug('Polling for user authorization.')
        data['code'] = device_code
        data['client_secret'] = CLIENT_SECRET
        end_time = time.time() + expires_in
        console('Waiting...', end='')
        # stop polling after expires_in seconds
        while time.time() < end_time:
            time.sleep(interval)
            polling_request = requests.post(get_api_url('oauth/device/token'), data=data,
                                            raise_status=False)
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
        'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob'
    }
    with Session() as session:
        acc = session.query(TraktUserAuth).filter(TraktUserAuth.account == account).first()
        if acc and datetime.now() < acc.expires and not refresh and not re_auth:
            return acc.access_token
        else:
            if acc and (refresh or datetime.now() >= acc.expires - timedelta(days=5)) and not re_auth:
                log.debug('Using refresh token to re-authorize account %s.', account)
                data['refresh_token'] = acc.refresh_token
                data['grant_type'] = 'refresh_token'
                token_dict = token_oauth(data)
            elif token:
                # We are only in here if a pin was specified, so it's safe to use console instead of logging
                console('Warning: PIN authorization has been deprecated. Use Device Authorization instead.')
                data['code'] = token
                data['grant_type'] = 'authorization_code'
                token_dict = token_oauth(data)
            elif called_from_cli:
                log.debug('No pin specified for an unknown account %s. Attempting to authorize device.', account)
                token_dict = device_auth()
            else:
                raise plugin.PluginError('Account %s has not been authorized. See `flexget trakt auth -h` on how to.' %
                                         account)
            try:
                new_acc = TraktUserAuth(account, token_dict['access_token'], token_dict['refresh_token'],
                                        token_dict.get('created_at', time.time()), token_dict['expires_in'])
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
    if len(endpoint) == 1 and not isinstance(endpoint[0], basestring):
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
                translation = session.query(trakt_translation).filter(and_(
                    trakt_translation.language == result.get('language'),
                    trakt_translation_id == ident)).first()
                if not translation:
                    translation = trakt_translation(result, session)
                translations.append(translation)
        return translations
    except requests.RequestException as e:
        log.debug('Error adding translations to trakt id %s: %s', ident, e)


class TraktGenre(Base):
    __tablename__ = 'trakt_genres'

    name = Column(Unicode, primary_key=True)


show_genres_table = Table('trakt_show_genres', Base.metadata,
                          Column('show_id', Integer, ForeignKey('trakt_shows.id')),
                          Column('genre_id', Unicode, ForeignKey('trakt_genres.name')))
Base.register_table(show_genres_table)

movie_genres_table = Table('trakt_movie_genres', Base.metadata,
                           Column('movie_id', Integer, ForeignKey('trakt_movies.id')),
                           Column('genre_id', Unicode, ForeignKey('trakt_genres.name')))
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
        return {
            'name': self.name,
            'trakt_id': self.id,
            'imdb_id': self.imdb,
            'tmdb_id': self.tmdb,
        }


show_actors_table = Table('trakt_show_actors', Base.metadata,
                          Column('show_id', Integer, ForeignKey('trakt_shows.id')),
                          Column('actors_id', Integer, ForeignKey('trakt_actors.id')))
Base.register_table(show_actors_table)

movie_actors_table = Table('trakt_movie_actors', Base.metadata,
                           Column('movie_id', Integer, ForeignKey('trakt_movies.id')),
                           Column('actors_id', Integer, ForeignKey('trakt_actors.id')))
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
        info = {
            'overview': lang.overview,
            'title': lang.title,
        }
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

        for col in ['title', 'number', 'episode_count', 'aired_episodes', 'ratings', 'votes', 'overview']:
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
    episodes = relation(TraktEpisode, backref='show', cascade='all, delete, delete-orphan', lazy='dynamic')
    seasons = relation(TraktSeason, backref='show', cascade='all, delete, delete-orphan', lazy='dynamic')
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
            "cached_at": self.cached_at
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

        for col in ['overview', 'runtime', 'rating', 'votes', 'language', 'title', 'year',
                    'runtime', 'certification', 'network', 'country', 'status', 'aired_episodes',
                    'trailer', 'homepage']:
            setattr(self, col, trakt_show.get(col))
        
        # Sometimes genres and translations are None but we really do want a list, hence the "or []"
        self.genres = [TraktGenre(name=g.replace(' ', '-')) for g in trakt_show.get('genres') or []]
        self.cached_at = datetime.now()
        self.translation_languages = trakt_show.get('available_translations') or []

    def get_episode(self, season, number, session, only_cached=False):
        # TODO: Does series data being expired mean all episode data should be refreshed?
        episode = self.episodes.filter(TraktEpisode.season == season).filter(TraktEpisode.number == number).first()
        if not episode or self.expired:
            url = get_api_url('shows', self.id, 'seasons', season, 'episodes', number, '?extended=full')
            if only_cached:
                raise LookupError('Episode %s %s not found in cache' % (season, number))
            log.debug('Episode %s %s not found in cache, looking up from trakt.', season, number)
            try:
                ses = get_session()
                data = ses.get(url).json()
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
                db_season = self.seasons.filter(TraktSeason.id == season_result['ids']['trakt']).first()
                if db_season:
                    db_season.update(season_result, session)
                else:
                    db_season = TraktSeason(season_result, session)
                    self.seasons.append(db_season)
                if number == season_result['number']:
                    season = db_season
            if not season:
                raise LookupError('Season %s not found for show %s' % (number, self.title))
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
            "cached_at": self.cached_at
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
        for col in ['title', 'overview', 'runtime', 'rating', 'votes',
                    'language', 'tagline', 'year', 'trailer', 'homepage']:
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


def split_title_year(title):
    """Splits title containing a year into a title, year pair."""
    # We only recognize years from the 2nd and 3rd millennium, FlexGetters from the year 3000 be damned!
    match = re.search(r'[\s(]([12]\d{3})\)?$', title)
    if match:
        title = title[:match.start()].strip()
        year = int(match.group(1))
    else:
        year = None
    return title, year


@with_session
def get_cached(style=None, title=None, year=None, trakt_id=None, trakt_slug=None, tmdb_id=None, imdb_id=None,
               tvdb_id=None, tvrage_id=None, session=None):
    """
    Get the cached info for a given show/movie from the database.
    :param type: Either 'show' or 'movie'
    """
    ids = {
        'id': trakt_id,
        'slug': trakt_slug,
        'tmdb_id': tmdb_id,
        'imdb_id': imdb_id,
    }
    if style == 'show':
        ids['tvdb_id'] = tvdb_id
        ids['tvrage_id'] = tvrage_id
        model = TraktShow
    else:
        model = TraktMovie
    result = None
    if any(ids.values()):
        result = session.query(model).filter(
            or_(getattr(model, col) == val for col, val in ids.items() if val)).first()
    elif title:
        title, y = split_title_year(title)
        year = year or y
        query = session.query(model).filter(model.title == title)
        if year:
            query = query.filter(model.year == year)
        result = query.first()
    return result


def get_trakt(style=None, title=None, year=None, trakt_id=None, trakt_slug=None, tmdb_id=None, imdb_id=None,
              tvdb_id=None, tvrage_id=None):
    """Returns the matching media object from trakt api."""
    # TODO: Better error messages
    # Trakt api accepts either id or slug (there is a rare possibility for conflict though, e.g. 24)
    trakt_id = trakt_id or trakt_slug
    if not any([title, trakt_id, tmdb_id, imdb_id, tvdb_id, tvrage_id]):
        raise LookupError('No lookup arguments provided.')
    req_session = get_session()
    last_search_query = None  # used if no results are found
    last_search_type = None
    if not trakt_id:
        # Try finding trakt_id based on other ids
        ids = {
            'imdb': imdb_id,
            'tmdb': tmdb_id
        }
        if style == 'show':
            ids['tvdb'] = tvdb_id
            ids['tvrage'] = tvrage_id
        for id_type, identifier in ids.items():
            if not identifier:
                continue
            try:
                last_search_query = identifier
                last_search_type = id_type
                log.debug('Searching with params: %s=%s', id_type, identifier)
                results = req_session.get(get_api_url('search'), params={'id_type': id_type, 'id': identifier}).json()
            except requests.RequestException as e:
                raise LookupError('Searching trakt for %s=%s failed with error: %s' % (id_type, identifier, e))
            for result in results:
                if result['type'] != style:
                    continue
                trakt_id = result[style]['ids']['trakt']
                break
        if not trakt_id and title:
            last_search_query = title
            last_search_type = 'title'
            # Try finding trakt id based on title and year
            if style == 'show':
                parsed_title, y = split_title_year(title)
                y = year or y
            else:
                title_parser = get_plugin_by_name('parsing').instance.parse_movie(title)
                y = year or title_parser.year
                parsed_title = title_parser.name
            try:
                params = {'query': parsed_title, 'type': style, 'year': y}
                log.debug('Type of title: %s', type(parsed_title))
                log.debug('Searching with params: %s', ', '.join('{}={}'.format(k, v) for (k, v) in params.items()))
                results = req_session.get(get_api_url('search'), params=params).json()
            except requests.RequestException as e:
                raise LookupError('Searching trakt for %s failed with error: %s' % (title, e))
            for result in results:
                if year and result[style]['year'] != year:
                    continue
                if parsed_title.lower() == result[style]['title'].lower():
                    trakt_id = result[style]['ids']['trakt']
                    break
            # grab the first result if there is no exact match
            if not trakt_id and results:
                trakt_id = results[0][style]['ids']['trakt']
    if not trakt_id:
        raise LookupError('Unable to find %s="%s" on trakt.' % (last_search_type, last_search_query))
    # Get actual data from trakt
    try:
        return req_session.get(get_api_url(style + 's', trakt_id), params={'extended': 'full'}).json()
    except requests.RequestException as e:
        raise LookupError('Error getting trakt data for id %s: %s' % (trakt_id, e))


def update_collection_cache(style_ident, username=None, account=None):
    if account and not username:
        username = 'me'
    url = get_api_url('users', username, 'collection', style_ident)
    session = get_session(account=account)
    try:
        data = session.get(url).json()
        if not data:
            log.warning('No collection data returned from trakt.')
            return
        cache = get_user_cache(username=username, account=account)['collection'][style_ident]
        log.verbose('Received %d records from trakt.tv %s\'s collection', len(data), username)
        if style_ident == 'movies':
            for movie in data:
                movie_id = movie['movie']['ids']['trakt']
                cache[movie_id] = movie['movie']
                cache[movie_id]['collected_at'] = dateutil_parse(movie['collected_at'], ignoretz=True)
        else:
            for series in data:
                series_id = series['show']['ids']['trakt']
                cache[series_id] = series['show']
                cache[series_id]['seasons'] = series['seasons']
                cache[series_id]['collected_at'] = dateutil_parse(series['last_collected_at'], ignoretz=True)
    except requests.RequestException as e:
        raise plugin.PluginError('Unable to get data from trakt.tv: %s' % e)


def update_watched_cache(style_ident, username=None, account=None):
    if account and not username:
        username = 'me'
    url = get_api_url('users', username, 'watched', style_ident)
    session = get_session(account=account)
    try:
        data = session.get(url).json()
        if not data:
            log.warning('No watched data returned from trakt.')
            return
        cache = get_user_cache(username=username, account=account)['watched'][style_ident]
        log.verbose('Received %d record(s) from trakt.tv %s\'s watched history', len(data), username)
        if style_ident == 'movies':
            for movie in data:
                movie_id = movie['movie']['ids']['trakt']
                cache[movie_id] = movie['movie']
                cache[movie_id]['watched_at'] = dateutil_parse(movie['last_watched_at'], ignoretz=True)
                cache[movie_id]['plays'] = movie['plays']
        else:
            for series in data:
                series_id = series['show']['ids']['trakt']
                cache[series_id] = series['show']
                cache[series_id]['seasons'] = series['seasons']
                cache[series_id]['watched_at'] = dateutil_parse(series['last_watched_at'], ignoretz=True)
                cache[series_id]['plays'] = series['plays']
    except requests.RequestException as e:
        raise plugin.PluginError('Unable to get data from trakt.tv: %s' % e)


def update_user_ratings_cache(style_ident, username=None, account=None):
    if account and not username:
        username = 'me'
    url = get_api_url('users', username, 'ratings', style_ident)
    session = get_session(account=account)
    try:
        data = session.get(url).json()
        if not data:
            log.warning('No user ratings data returned from trakt.')
            return
        cache = get_user_cache(username=username, account=account)['user_ratings']
        log.verbose('Received %d record(s) from trakt.tv %s\'s %s user ratings', len(data), username, style_ident)
        for item in data:
            # get the proper cache from the type returned by trakt
            item_type = item['type']
            item_cache = cache[item_type + 's']

            # season cannot be put into shows because the code would turn to spaghetti later when retrieving from cache
            # instead we put some season info inside the season cache key'd to series id
            # eg. cache['seasons'][<show_id>][<season_number>] = ratings and stuff
            if item_type == 'season':
                show_id = item['show']['ids']['trakt']
                season = item['season']['number']
                item_cache.setdefault(show_id, {})
                item_cache[show_id].setdefault(season, {})
                item_cache = item_cache[show_id]
                item_id = season
            else:
                item_id = item[item_type]['ids']['trakt']
            item_cache[item_id] = item[item_type]
            item_cache[item_id]['rated_at'] = dateutil_parse(item['rated_at'], ignoretz=True)
            item_cache[item_id]['rating'] = item['rating']
    except requests.RequestException as e:
        raise plugin.PluginError('Unable to get data from trakt.tv: %s' % e)


def get_user_cache(username=None, account=None):
    identifier = '{}|{}'.format(account, username or 'me')
    ApiTrakt.user_cache.setdefault(identifier, {}).setdefault('watched', {}).setdefault('shows', {})
    ApiTrakt.user_cache.setdefault(identifier, {}).setdefault('watched', {}).setdefault('movies', {})
    ApiTrakt.user_cache.setdefault(identifier, {}).setdefault('collection', {}).setdefault('shows', {})
    ApiTrakt.user_cache.setdefault(identifier, {}).setdefault('collection', {}).setdefault('movies', {})
    ApiTrakt.user_cache.setdefault(identifier, {}).setdefault('user_ratings', {}).setdefault('shows', {})
    ApiTrakt.user_cache.setdefault(identifier, {}).setdefault('user_ratings', {}).setdefault('seasons', {})
    ApiTrakt.user_cache.setdefault(identifier, {}).setdefault('user_ratings', {}).setdefault('episodes', {})
    ApiTrakt.user_cache.setdefault(identifier, {}).setdefault('user_ratings', {}).setdefault('movies', {})

    return ApiTrakt.user_cache[identifier]


class ApiTrakt(object):
    user_cache = TimedDict(cache_time='15 minutes')

    @staticmethod
    @with_session
    def lookup_series(session=None, only_cached=None, **lookup_params):
        series = get_cached('show', session=session, **lookup_params)
        title = lookup_params.get('title') or ''
        found = None
        if not series and title:
            found = session.query(TraktShowSearchResult).filter(TraktShowSearchResult.search == title.lower()).first()
            if found and found.series:
                log.debug('Found %s in previous search results as %s', title, found.series.title)
                series = found.series
        if only_cached:
            if series:
                return series
            raise LookupError('Series %s not found from cache' % lookup_params)
        if series and not series.expired:
            return series
        try:
            trakt_show = get_trakt('show', **lookup_params)
        except LookupError as e:
            if series:
                log.debug('Error refreshing show data from trakt, using cached. %s', e)
                return series
            raise
        series = session.merge(TraktShow(trakt_show, session))
        if series and title.lower() == series.title.lower():
            return series
        elif series and title and not found:
            if not session.query(TraktShowSearchResult).filter(TraktShowSearchResult.search == title.lower()).first():
                log.debug('Adding search result to db')
                session.merge(TraktShowSearchResult(search=title, series=series))
        elif series and found:
            log.debug('Updating search result in db')
            found.series = series
        return series

    @staticmethod
    @with_session
    def lookup_movie(session=None, only_cached=None, **lookup_params):
        movie = get_cached('movie', session=session, **lookup_params)
        title = lookup_params.get('title') or ''
        found = None
        if not movie and title:
            found = session.query(TraktMovieSearchResult).filter(TraktMovieSearchResult.search == title.lower()).first()
            if found and found.movie:
                log.debug('Found %s in previous search results as %s', title, found.movie.title)
                movie = found.movie
        if only_cached:
            if movie:
                return movie
            raise LookupError('Movie %s not found from cache' % lookup_params)
        if movie and not movie.expired:
            return movie
        try:
            trakt_movie = get_trakt('movie', **lookup_params)
        except LookupError as e:
            if movie:
                log.debug('Error refreshing movie data from trakt, using cached. %s', e)
                return movie
            raise
        movie = session.merge(TraktMovie(trakt_movie, session))
        if movie and title.lower() == movie.title.lower():
            return movie
        if movie and title and not found:
            if not session.query(TraktMovieSearchResult).filter(TraktMovieSearchResult.search == title.lower()).first():
                log.debug('Adding search result to db')
                session.merge(TraktMovieSearchResult(search=title, movie=movie))
        elif movie and found:
            log.debug('Updating search result in db')
            found.movie = movie
        return movie

    @staticmethod
    def collected(style, trakt_data, title, username=None, account=None):
        style_ident = 'movies' if style == 'movie' else 'shows'
        cache = get_user_cache(username=username, account=account)
        if not cache['collection'][style_ident]:
            log.debug('No collection found in cache.')
            update_collection_cache(style_ident, username=username, account=account)
        if not cache['collection'][style_ident]:
            log.warning('No collection data returned from trakt.')
            return
        in_collection = False
        cache = cache['collection'][style_ident]
        if style == 'show':
            if trakt_data.id in cache:
                series = cache[trakt_data.id]
                # specials are not included
                number_of_collected_episodes = sum(len(s['episodes']) for s in series['seasons'] if s['number'] > 0)
                in_collection = number_of_collected_episodes >= trakt_data.aired_episodes
        elif style == 'episode':
            if trakt_data.show.id in cache:
                series = cache[trakt_data.show.id]
                for s in series['seasons']:
                    if s['number'] == trakt_data.season:
                        # extract all episode numbers currently in collection for the season number
                        episodes = [ep['number'] for ep in s['episodes']]
                        in_collection = trakt_data.number in episodes
                        break
        elif style == 'season':
            if trakt_data.show.id in cache:
                series = cache[trakt_data.show.id]
                for s in series['seasons']:
                    if trakt_data.number == s['number']:
                        in_collection = True
                        break
        else:
            if trakt_data.id in cache:
                in_collection = True
        log.debug('The result for entry "%s" is: %s', title,
                  'Owned' if in_collection else 'Not owned')
        return in_collection

    @staticmethod
    def watched(style, trakt_data, title, username=None, account=None):
        style_ident = 'movies' if style == 'movie' else 'shows'
        cache = get_user_cache(username=username, account=account)
        if not cache['watched'][style_ident]:
            log.debug('No watched history found in cache.')
            update_watched_cache(style_ident, username=username, account=account)
        if not cache['watched'][style_ident]:
            log.warning('No watched data returned from trakt.')
            return
        watched = False
        cache = cache['watched'][style_ident]
        if style == 'show':
            if trakt_data.id in cache:
                series = cache[trakt_data.id]
                # specials are not included
                number_of_watched_episodes = sum(len(s['episodes']) for s in series['seasons'] if s['number'] > 0)
                watched = number_of_watched_episodes == trakt_data.aired_episodes
        elif style == 'episode':
            if trakt_data.show.id in cache:
                series = cache[trakt_data.show.id]
                for s in series['seasons']:
                    if s['number'] == trakt_data.season:
                        # extract all episode numbers currently in collection for the season number
                        episodes = [ep['number'] for ep in s['episodes']]
                        watched = trakt_data.number in episodes
                        break
        elif style == 'season':
            if trakt_data.show.id in cache:
                series = cache[trakt_data.show.id]
                for s in series['seasons']:
                    if trakt_data.number == s['number']:
                        watched = True
                        break
        else:
            if trakt_data.id in cache:
                watched = True
        log.debug('The result for entry "%s" is: %s', title,
                  'Watched' if watched else 'Not watched')
        return watched

    @staticmethod
    def user_ratings(style, trakt_data, title, username=None, account=None):
        style_ident = style + 's'
        cache = get_user_cache(username=username, account=account)
        if not cache['user_ratings'][style_ident]:
            log.debug('No user ratings found in cache.')
            update_user_ratings_cache(style_ident, username=username, account=account)
        if not cache['user_ratings'][style_ident]:
            log.warning('No user ratings data returned from trakt.')
            return
        user_rating = None
        cache = cache['user_ratings'][style_ident]
        # season ratings are a little annoying and require butchering the code
        if style == 'season' and trakt_data.series_id in cache:
            if trakt_data.number in cache[trakt_data.series_id]:
                user_rating = cache[trakt_data.series_id][trakt_data.number]['rating']
        if trakt_data.id in cache:
            user_rating = cache[trakt_data.id]['rating']
        log.debug('User rating for entry "%s" is: %s', title, user_rating)
        return user_rating


@event('plugin.register')
def register_plugin():
    plugin.register(ApiTrakt, 'api_trakt', api_ver=2, interfaces=[])
