from __future__ import unicode_literals, division, absolute_import
import logging
import urllib
import os
import posixpath
from datetime import datetime, timedelta
import random

import xml.etree.ElementTree as ElementTree
try:
    from xml.etree.ElementTree import ParseError
except ImportError:
    # Python 2.6 throws this instead when there is invalid xml
    from xml.parsers.expat import ExpatError as ParseError

from sqlalchemy import Column, Integer, Float, String, Unicode, Boolean, DateTime, func
from sqlalchemy.schema import ForeignKey
from sqlalchemy.orm import relation
from requests import RequestException

from flexget import db_schema
from flexget.utils.tools import decode_html
from flexget.utils.requests import Session as ReqSession
from flexget.utils.database import with_session, pipe_list_synonym, text_date_synonym
from flexget.utils.sqlalchemy_utils import table_add_column
from flexget.manager import Session
from flexget.utils.simple_persistence import SimplePersistence

SCHEMA_VER = 4

log = logging.getLogger('api_tvdb')
Base = db_schema.versioned_base('api_tvdb', SCHEMA_VER)
requests = ReqSession(timeout=25)

# This is a FlexGet API key
api_key = '4D297D8CFDE0E105'
language = 'en'
server = 'http://www.thetvdb.com/api/'
_mirrors = {}
persist = SimplePersistence('api_tvdb')


@db_schema.upgrade('api_tvdb')
def upgrade(ver, session):
    if ver is None:
        if 'last_updated' in persist:
            del persist['last_updated']
        ver = 0
    if ver == 0:
        table_add_column('tvdb_episodes', 'gueststars', Unicode, session)
        ver = 1
    if ver == 1:
        table_add_column('tvdb_episodes', 'absolute_number', Integer, session)
        ver = 2
    if ver == 2:
        table_add_column('tvdb_series', 'overview', Unicode, session)
        ver = 3
    if ver == 3:
        table_add_column('tvdb_series', 'actors', Unicode, session)
        ver = 4

    return ver


def get_mirror(type='xml'):
    """Returns a random mirror for a given type 'xml', 'zip', or 'banner'"""
    global _mirrors
    if not _mirrors.get(type):
        # Get the list of mirrors from tvdb
        page = None
        try:
            page = requests.get(server + api_key + '/mirrors.xml').content
        except RequestException:
            pass
        # If there were problems getting the mirror list we'll just fall back to the main site.
        if page:
            data = ElementTree.fromstring(page)
            for mirror in data.findall('Mirror'):
                type_mask = int(mirror.find("typemask").text)
                mirrorpath = mirror.find("mirrorpath").text
                for t in [(1, 'xml'), (2, 'banner'), (4, 'zip')]:
                    if type_mask & t[0]:
                        _mirrors.setdefault(t[1], set()).add(mirrorpath)
        else:
            log.debug('Unable to get the mirrors list from thetvdb.')
    if _mirrors.get(type):
        return random.sample(_mirrors[type], 1)[0] + ('/banners/' if type == 'banner' else '/api/')
    else:
        # If nothing was populated from the server's mirror list, return the main site as fallback
        return 'http://thetvdb.com' + ('/banners/' if type == 'banner' else '/api/')


class TVDBContainer(object):
    """Base class for TVDb objects"""

    def __init__(self, init_xml=None):
        if init_xml is not None:
            self.update_from_xml(init_xml)

    def update_from_xml(self, update_xml):
        """Populates any simple (string or number) attributes from a dict"""
        for node in update_xml:
            if not node.text or not node.tag:
                continue

            # Have to iterate to get around the inability to do a case-insensitive find
            for col in self.__table__.columns:
                if node.tag.lower() == col.name.lower():
                    if isinstance(col.type, Integer):
                        value = int(node.text)
                    elif isinstance(col.type, Float):
                        value = float(node.text)
                    else:
                        # Make sure we always have unicode strings
                        value = node.text.decode('utf-8') if isinstance(node.text, str) else node.text
                        value = decode_html(value)
                    setattr(self, col.name, value)
        self.expired = False


class TVDBSeries(TVDBContainer, Base):

    __tablename__ = "tvdb_series"

    id = Column(Integer, primary_key=True, autoincrement=False)
    lastupdated = Column(Integer)
    expired = Column(Boolean)
    seriesname = Column(Unicode)
    language = Column(Unicode)
    rating = Column(Float)
    status = Column(Unicode)
    runtime = Column(Integer)
    airs_time = Column(Unicode)
    airs_dayofweek = Column(Unicode)
    contentrating = Column(Unicode)
    network = Column(Unicode)
    overview = Column(Unicode)
    imdb_id = Column(String)
    zap2it_id = Column(String)
    banner = Column(String)
    fanart = Column(String)
    poster = Column(String)
    poster_file = Column(Unicode)
    _genre = Column('genre', Unicode)
    genre = pipe_list_synonym('_genre')
    _firstaired = Column('firstaired', DateTime)
    firstaired = text_date_synonym('_firstaired')
    _actors = Column('actors', Unicode)
    actors = pipe_list_synonym('_actors')

    episodes = relation('TVDBEpisode', backref='series', cascade='all, delete, delete-orphan')

    def update(self, tvdb_id=None):
        tvdb_id = tvdb_id or self.id
        url = get_mirror() + api_key + '/series/%s/%s.xml' % (tvdb_id, language)
        try:
            data = requests.get(url).content
        except RequestException as e:
            raise LookupError('Request failed %s' % url)
        result = ElementTree.fromstring(data).find('Series')
        if result is not None:
            self.update_from_xml(result)
        else:
            raise LookupError('Could not retrieve information from thetvdb')

    def get_poster(self, only_cached=False):
        """Downloads this poster to a local cache and returns the path"""
        from flexget.manager import manager
        base_dir = os.path.join(manager.config_base, 'userstatic')
        if os.path.isfile(os.path.join(base_dir, self.poster_file or '')):
            return self.poster_file
        elif only_cached:
            return
        # If we don't already have a local copy, download one.
        url = get_mirror('banner') + self.poster
        log.debug('Downloading poster %s' % url)
        dirname = os.path.join('tvdb', 'posters')
        # Create folders if the don't exist
        fullpath = os.path.join(base_dir, dirname)
        if not os.path.isdir(fullpath):
            os.makedirs(fullpath)
        filename = os.path.join(dirname, posixpath.basename(self.poster))
        thefile = file(os.path.join(base_dir, filename), 'wb')
        thefile.write(requests.get(url).content)
        self.poster_file = filename
        # If we are detached from a session, update the db
        if not Session.object_session(self):
            with Session() as session:
                session.query(TVDBSeries).filter(TVDBSeries.id == self.id).update(values={'poster_file': filename})
        return filename

    def __repr__(self):
        return '<TVDBSeries name=%s,tvdb_id=%s>' % (self.seriesname, self.id)


class TVDBEpisode(TVDBContainer, Base):
    __tablename__ = 'tvdb_episodes'

    id = Column(Integer, primary_key=True, autoincrement=False)
    expired = Column(Boolean)
    lastupdated = Column(Integer)
    seasonnumber = Column(Integer)
    episodenumber = Column(Integer)
    absolute_number = Column(Integer)
    episodename = Column(Unicode)
    overview = Column(Unicode)
    _director = Column('director', Unicode)
    director = pipe_list_synonym('_director')
    _writer = Column('writer', Unicode)
    writer = pipe_list_synonym('_writer')
    _gueststars = Column('gueststars', Unicode)
    gueststars = pipe_list_synonym('_gueststars')
    rating = Column(Float)
    filename = Column(Unicode)
    _firstaired = Column('firstaired', DateTime)
    firstaired = text_date_synonym('_firstaired')

    series_id = Column(Integer, ForeignKey('tvdb_series.id'), nullable=False)

    def update(self):
        if not self.id:
            raise LookupError('Cannot update an episode without an episode id.')
        url = get_mirror() + api_key + '/episodes/%s/%s.xml' % (self.id, language)
        try:
            data = requests.get(url).content
        except RequestException as e:
            raise LookupError('Request failed %s' % url)
        result = ElementTree.fromstring(data).find('Episode')
        if result is not None:
            self.update_from_xml(result)
        else:
            raise LookupError('Could not retrieve information from thetvdb')

    def __repr__(self):
        return '<TVDBEpisode series=%s,season=%s,episode=%s>' %\
               (self.series.seriesname, self.seasonnumber, self.episodenumber)


class TVDBSearchResult(Base):

    __tablename__ = 'tvdb_search_results'

    id = Column(Integer, primary_key=True)
    search = Column(Unicode, nullable=False)
    series_id = Column(Integer, ForeignKey('tvdb_series.id'), nullable=True)
    series = relation(TVDBSeries, backref='search_strings')


def find_series_id(name):
    """Looks up the tvdb id for a series"""
    url = server + 'GetSeries.php?seriesname=%s&language=%s' % (urllib.quote(name), language)
    try:
        page = requests.get(url).content
    except RequestException as e:
        raise LookupError('Unable to get search results for %s: %s' % (name, e))
    try:
        xmldata = ElementTree.fromstring(page)
    except ParseError as e:
        log.error('error parsing tvdb result for %s: %s' % (name, e))
        return
    if xmldata is None:
        log.error("Didn't get a return from tvdb on the series search for %s" % name)
        return
    # See if there is an exact match
    # TODO: Check if there are multiple exact matches
    firstmatch = xmldata.find('Series')
    if firstmatch is not None and firstmatch.find("SeriesName").text.lower() == name.lower():
        return int(firstmatch.find("seriesid").text)
    # If there is no exact match, sort by airing date and pick the latest
    # TODO: Is there a better way to do this? Maybe weight name similarity and air date
    series_list = []
    for s in xmldata.findall('Series'):
        fa = s.find("FirstAired")
        if fa is not None and fa.text:
            series_list.append((fa.text, s.find("seriesid").text))

    if series_list:
        series_list.sort(key=lambda s: s[0], reverse=True)
        return int(series_list[0][1])
    else:
        raise LookupError('No results for `%s`' % name)


@with_session(expire_on_commit=False)
def lookup_series(name=None, tvdb_id=None, only_cached=False, session=None):
    """
    Look up information on a series. Will be returned from cache if available, and looked up online and cached if not.

    Either `name` or `tvdb_id` parameter are needed to specify the series.
    :param unicode name: Name of series.
    :param int tvdb_id: TVDb ID of series.
    :param bool only_cached: If True, will not cause an online lookup. LookupError will be raised if not available
        in the cache.
    :param session: An sqlalchemy session to be used to lookup and store to cache. Commit(s) may occur when passing in
        a session. If one is not supplied it will be created.

    :return: Instance of :class:`TVDBSeries` populated with series information. If session was not supplied, this will
        be a detached from the database, so relationships cannot be loaded.
    :raises: :class:`LookupError` if series cannot be looked up.
    """
    if not (name or tvdb_id):
        raise LookupError('No criteria specified for tvdb lookup')

    log.debug('Looking up tvdb information for %r' % {'name': name, 'tvdb_id': tvdb_id})

    series = None

    def id_str():
        return '<name=%s,tvdb_id=%s>' % (name, tvdb_id)

    if tvdb_id:
        series = session.query(TVDBSeries).filter(TVDBSeries.id == tvdb_id).first()
    if not series and name:
        series = session.query(TVDBSeries).filter(func.lower(TVDBSeries.seriesname) == name.lower()).first()
        if not series:
            found = session.query(TVDBSearchResult).filter(
                func.lower(TVDBSearchResult.search) == name.lower()).first()
            if found and found.series:
                series = found.series
    if series:
        # Series found in cache, update if cache has expired.
        if not only_cached:
            mark_expired(session=session)
        if not only_cached and series.expired:
            log.verbose('Data for %s has expired, refreshing from tvdb' % series.seriesname)
            try:
                series.update()
            except LookupError as e:
                log.warning('Error while updating from tvdb (%s), using cached data.' % e.args[0])
        else:
            log.debug('Series %s information restored from cache.' % id_str())
    else:
        if only_cached:
            raise LookupError('Series %s not found from cache' % id_str())
        # There was no series found in the cache, do a lookup from tvdb
        log.debug('Series %s not found in cache, looking up from tvdb.' % id_str())
        if tvdb_id:
            series = TVDBSeries()
            series.update(tvdb_id)
            if series.seriesname:
                session.add(series)
        elif name:
            tvdb_id = find_series_id(name)
            if tvdb_id:
                series = session.query(TVDBSeries).filter(TVDBSeries.id == tvdb_id).first()
                if not series:
                    series = TVDBSeries()
                    series.update(tvdb_id)
                    session.add(series)
                if name.lower() != series.seriesname.lower():
                    session.add(TVDBSearchResult(search=name, series=series))

    if not series:
        raise LookupError('No results found from tvdb for %s' % id_str())
    if not series.seriesname:
        raise LookupError('Tvdb result for series does not have a title.')
    session.commit()
    return series


@with_session(expire_on_commit=False)
def lookup_episode(name=None, seasonnum=None, episodenum=None, absolutenum=None, airdate=None,
                   tvdb_id=None, only_cached=False, session=None):
    """
    Look up information on an episode. Will be returned from cache if available, and looked up online and cached if not.

    Either `name` or `tvdb_id` parameter are needed to specify the series.
    Either `seasonnum` and `episodedum`, `absolutenum`, or `airdate` are required to specify episode number.
    :param unicode name: Name of series episode belongs to.
    :param int tvdb_id: TVDb ID of series episode belongs to.
    :param int seasonnum: Season number of episode.
    :param int episodenum: Episode number of episode.
    :param int absolutenum: Absolute number of episode.
    :param int airdate: Air date of episode.
    :param bool only_cached: If True, will not cause an online lookup. LookupError will be raised if not available
        in the cache.
    :param session: An sqlalchemy session to be used to lookup and store to cache. Commit(s) may occur when passing in
        a session. If one is not supplied it will be created, however if you need to access relationships you should
        pass one in.

    :return: Instance of :class:`TVDBEpisode` populated with series information.
    :raises: :class:`LookupError` if episode cannot be looked up.
    """
    # First make sure we have the series data
    series = lookup_series(name=name, tvdb_id=tvdb_id, only_cached=only_cached, session=session)
    # Set variables depending on what type of identifier we are looking up
    if airdate is not None:
        airdatestring = airdate.strftime('%Y-%m-%d')
        ep_description = '%s.%s' % (series.seriesname, airdatestring)
        episode = session.query(TVDBEpisode).filter(TVDBEpisode.series_id == series.id).\
            filter(TVDBEpisode.firstaired == airdate).first()
        url = get_mirror() + ('GetEpisodeByAirDate.php?apikey=%s&seriesid=%d&airdate=%s&language=%s' %
                             (api_key, series.id, airdatestring, language))
    elif absolutenum is not None:
        ep_description = '%s.%d' % (series.seriesname, absolutenum)
        episode = session.query(TVDBEpisode).filter(TVDBEpisode.series_id == series.id).\
            filter(TVDBEpisode.absolute_number == absolutenum).first()
        url = get_mirror() + api_key + '/series/%d/absolute/%s/%s.xml' % (series.id, absolutenum, language)
    elif seasonnum is not None and episodenum is not None:
        ep_description = '%s.S%sE%s' % (series.seriesname, seasonnum, episodenum)
        # See if we have this episode cached
        episode = session.query(TVDBEpisode).filter(TVDBEpisode.series_id == series.id).\
            filter(TVDBEpisode.seasonnumber == seasonnum).\
            filter(TVDBEpisode.episodenumber == episodenum).first()
        url = get_mirror() + api_key + '/series/%d/default/%d/%d/%s.xml' % (series.id, seasonnum, episodenum, language)
    else:
        raise LookupError('No episode identifier specified.')
    if episode:
        if episode.expired and not only_cached:
            log.info('Data for %r has expired, refreshing from tvdb' % episode)
            try:
                episode.update()
            except LookupError as e:
                log.warning('Error while updating from tvdb (%s), using cached data.' % e.args[0])
        else:
            log.debug('Using episode info for %s from cache.' % ep_description)
    else:
        if only_cached:
            raise LookupError('Episode %s not found from cache' % ep_description)
        # There was no episode found in the cache, do a lookup from tvdb
        log.debug('Episode %s not found in cache, looking up from tvdb.' % ep_description)
        try:
            raw_data = requests.get(url).content
            data = ElementTree.fromstring(raw_data)
            if data is not None:
                error = data.find('Error') # TODO: lowercase????
                if error is not None:
                    raise LookupError('Error looking up episode from TVDb (%s)' % error.text)
                ep_data = data.find('Episode')
                if ep_data is not None:
                    # Check if this episode id is already in our db
                    episode = session.query(TVDBEpisode).filter(TVDBEpisode.id == ep_data.find("id").text).first()
                    if episode is not None:
                        episode.update_from_xml(ep_data)
                    else:
                        episode = TVDBEpisode(ep_data)
                    series.episodes.append(episode)
                    session.merge(series)
        except RequestException as e:
            raise LookupError('Error looking up episode from TVDb (%s)' % e)
    if episode:
        session.commit()
        return episode
    else:
        raise LookupError('No results found for ')


@with_session
def mark_expired(session=None):
    """Marks series and episodes that have expired since we cached them"""
    # Only get the expired list every hour
    last_server = persist.get('last_server')
    last_local = persist.get('last_local')

    if not last_local:
        # Never run before? Lets reset ALL series
        log.info('Setting all series to expire')
        session.query(TVDBSeries).update({'expired': True}, synchronize_session='fetch')
        persist['last_local'] = datetime.now()
        return
    elif last_local + timedelta(hours=6) > datetime.now():
        # It has been less than an hour, don't check again yet
        return

    if not last_server:
        last_server = 0

    # Need to figure out what type of update file to use
    # Default of day
    get_update = 'day'
    last_update_days = (datetime.now() - last_local).days

    if 1 < last_update_days < 7:
        get_update = 'week'
    elif last_update_days > 7:
        get_update = 'month'

    try:
        # Get items that have changed since our last update
        log.debug("Getting %s worth of updates from thetvdb" % get_update)
        content = requests.get(server + api_key + '/updates/updates_%s.xml' % get_update).content
        if not isinstance(content, basestring):
            raise Exception('expected string, got %s' % type(content))
        updates = ElementTree.fromstring(content)
    except RequestException as e:
        log.error('Could not get update information from tvdb: %s' % e)
        return

    if updates is not None:
        new_server = int(updates.attrib['time'])

        if new_server <= last_server:
            # nothing changed on the server, ignoring
            log.debug("Not checking for expired as nothing has changed on server")
            return

        # Make lists of expired series and episode ids
        expired_series = []
        expired_episodes = []

        for series in updates.findall('Series'):
            expired_series.append(int(series.find("id").text))

        for episode in updates.findall('Episode'):
            expired_series.append(int(episode.find("id").text))

        def chunked(seq):
            """Helper to divide our expired lists into sizes sqlite can handle in a query. (<1000)"""
            for i in xrange(0, len(seq), 900):
                yield seq[i:i + 900]

        # Update our cache to mark the items that have expired
        for chunk in chunked(expired_series):
            num = session.query(TVDBSeries).filter(TVDBSeries.id.in_(chunk)).update({'expired': True}, 'fetch')
            log.debug('%s series marked as expired' % num)
        for chunk in chunked(expired_episodes):
            num = session.query(TVDBEpisode).filter(TVDBEpisode.id.in_(chunk)).update({'expired': True}, 'fetch')
            log.debug('%s episodes marked as expired' % num)

        # Save the time of this update
        session.commit()
        persist['last_local'] = datetime.now()
        persist['last_server'] = new_server
