import logging
import urllib
import os
import posixpath
from datetime import datetime, timedelta
from urllib2 import URLError
from random import sample
from BeautifulSoup import BeautifulStoneSoup
from sqlalchemy import Column, Integer, Float, String, Unicode, Boolean, DateTime, func
from sqlalchemy.schema import ForeignKey
from sqlalchemy.orm import relation
from flexget import schema
from flexget.utils.tools import urlopener
from flexget.utils.database import with_session, pipe_list_synonym, text_date_synonym
from flexget.manager import Session
from flexget.utils.simple_persistence import SimplePersistence

log = logging.getLogger('api_tvdb')
Base = schema.versioned_base('api_tvdb', 0)

# This is a FlexGet API key
api_key = '4D297D8CFDE0E105'
language = 'en'
server = 'http://www.thetvdb.com/api/'
_mirrors = {}
persist = SimplePersistence('api_tvdb')


@schema.upgrade('api_tvdb')
def upgrade(ver, session):
    if ver is None:
        if 'last_updated' in persist:
            del persist['last_updated']
        ver = 0
    return ver


def get_mirror(type='xml'):
    """Returns a random mirror for a given type 'xml', 'zip', or 'banner'"""
    global _mirrors
    if not _mirrors.get(type):
        # Get the list of mirrors from tvdb
        try:
            data = BeautifulStoneSoup(urlopener(server + api_key + '/mirrors.xml', log))
        except URLError:
            raise LookupError('Could not retrieve mirror list from thetvdb')
        for mirror in  data.findAll('mirror'):
            type_mask = int(mirror.typemask.string)
            mirrorpath = mirror.mirrorpath.string
            for t in [(1, 'xml'), (2, 'banner'), (4, 'zip')]:
                if type_mask & t[0]:
                    _mirrors.setdefault(t[1], set()).add(mirrorpath)
    if _mirrors.get(type):
        return sample(_mirrors[type], 1)[0] + ('/banners/' if type == 'banner' else '/api/')


class TVDBContainer(object):
    """Base class for TVDb objects"""

    def __init__(self, init_bss=None):
        if init_bss:
            self.update_from_bss(init_bss)

    def update_from_bss(self, update_bss):
        """Populates any simple (string or number) attributes from a dict"""
        for col in self.__table__.columns:
            tag = update_bss.find(col.name)
            if tag:
                if tag.string:
                    setattr(self, col.name, tag.string)
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

    episodes = relation('TVDBEpisode', backref='series', cascade='all, delete, delete-orphan')

    def update(self):
        if not self.id:
            raise LookupError('Cannot update a series without a tvdb id.')
        url = get_mirror() + api_key + '/series/%s/%s.xml' % (self.id, language)
        try:
            data = urlopener(url, log)
        except URLError, e:
            raise LookupError('Request failed %s' % url)
        result = BeautifulStoneSoup(data, convertEntities=BeautifulStoneSoup.HTML_ENTITIES).find('series')
        if result:
            self.update_from_bss(result)
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
        thefile.write(urlopener(url, log).read())
        self.poster_file = filename
        # If we are detached from a session, update the db
        if not Session.object_session(self):
            session = Session()
            session.query(TVDBSeries).filter(TVDBSeries.id == self.id).update(values={'poster_file': filename})
            session.close()
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
    episodename = Column(Unicode)
    overview = Column(Unicode)
    _director = Column('director', Unicode)
    director = pipe_list_synonym('_director')
    _writer = Column('writer', Unicode)
    writer = pipe_list_synonym('_writer')
    _guest_stars = Column('guest_stars', Unicode)
    guest_stars = pipe_list_synonym('_guest_stars')
    rating = Column(Float)
    filename = Column(Unicode)
    _firstaired = Column('firstaired', DateTime)
    firstaired = text_date_synonym('_firstaired')

    series_id = Column(Integer, ForeignKey('tvdb_series.id'), nullable=False)

    def update(self):
        if not self.id:
            raise LookupError('Cannot update an episode without an episode id.')
        url = get_mirror() + api_key + '/episodes/%s/%s.xml' % (self.id, language)
        from urllib2 import URLError
        try:
            data = urlopener(url, log)
        except URLError, e:
            raise LookupError('Request failed %s' % url)
        result = BeautifulStoneSoup(data).find('episode')
        if result:
            self.update_from_bss(result)
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
        page = urlopener(url, log)
    except URLError, e:
        raise LookupError("Unable to get search results for %s: %s" % (name, e))
    xmldata = BeautifulStoneSoup(page).data
    if not xmldata:
        log.error("Didn't get a return from tvdb on the series search for %s" % name)
        return
    # See if there is an exact match
    # TODO: Check if there are multiple exact matches
    firstmatch = xmldata.find('series')
    if firstmatch and firstmatch.seriesname.string.lower() == name.lower():
        return firstmatch.seriesid.string
    # If there is no exact match, sort by airing date and pick the latest
    # TODO: Is there a better way to do this? Maybe weight name similarity and air date
    series_list = [(s.firstaired.string, s.seriesid.string) for s in xmldata.findAll('series', recursive=False) if s.firstaired]
    if series_list:
        series_list.sort(key=lambda s: s[0], reverse=True)
        return series_list[0][1]
    else:
        raise LookupError('No results for `%s`' % name)


@with_session
def lookup_series(name=None, tvdb_id=None, only_cached=False, session=None):
    if not name and not tvdb_id:
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
            found = session.query(TVDBSearchResult). \
                    filter(func.lower(TVDBSearchResult.search) == name.lower()).first()
            if found and found.series:
                series = found.series
    if series:
        # Series found in cache, update if cache has expired.
        if not only_cached:
            mark_expired(session=session)
        if series.expired and not only_cached:
            log.info('Data for %s has expired, refreshing from tvdb' % series.seriesname)
            try:
                series.update()
            except LookupError, e:
                log.warning('Error while updating from tvdb (%s), using cached data.' % e.message)
        else:
            log.debug('Series %s information restored from cache.' % id_str())
    else:
        if only_cached:
            raise LookupError('Series %s not found from cache' % id_str())
        # There was no series found in the cache, do a lookup from tvdb
        log.debug('Series %s not found in cache, looking up from tvdb.' % id_str())
        try:
            if tvdb_id:
                series = TVDBSeries()
                series.id = tvdb_id
                series.update()
                if series.seriesname:
                    session.add(series)
            elif name:
                tvdb_id = find_series_id(name)
                if tvdb_id:
                    series = session.query(TVDBSeries).filter(TVDBSeries.id == tvdb_id).first()
                    if not series:
                        series = TVDBSeries()
                        series.id = tvdb_id
                        series.update()
                        session.add(series)
                    if name.lower() != series.seriesname.lower():
                        session.add(TVDBSearchResult(search=name, series=series))
        except URLError, e:
            raise LookupError('Error looking up series from TVDb (%s)' % e)

    if not series:
        raise LookupError('No results found from tvdb for %s' % id_str())
    else:
        series.episodes
        return series


@with_session
def lookup_episode(name=None, seasonnum=None, episodenum=None, tvdb_id=None, only_cached=False, session=None):
    # First make sure we have the series data
    series = lookup_series(name=name, tvdb_id=tvdb_id, only_cached=only_cached, session=session)
    if not series:
        raise LookupError('Could not identify series')
    ep_description = '%s.S%sE%s' % (series.seriesname, seasonnum, episodenum)
    # See if we have this episode cached
    episode = session.query(TVDBEpisode).filter(TVDBEpisode.series_id == series.id).\
                                         filter(TVDBEpisode.seasonnumber == seasonnum).\
                                         filter(TVDBEpisode.episodenumber == episodenum).first()
    if episode:
        if episode.expired and not only_cached:
            log.info('Data for %r has expired, refreshing from tvdb' % episode)
            try:
                episode.update()
            except LookupError, e:
                log.warning('Error while updating from tvdb (%s), using cached data.' % e.message)
        else:
            log.debug('Using episode info from cache.')
    else:
        if only_cached:
            raise LookupError('Episode %s not found from cache' % ep_description)
        # There was no episode found in the cache, do a lookup from tvdb
        log.debug('Episode %s not found in cache, looking up from tvdb.' % ep_description)
        url = get_mirror() + api_key + '/series/%d/default/%d/%d/%s.xml' % (series.id, seasonnum, episodenum, language)
        try:
            data = BeautifulStoneSoup(urlopener(url, log)).data
            if data:
                ep_data = data.find('episode')
                if ep_data:
                    # Check if this episode id is already in our db
                    episode = session.query(TVDBEpisode).filter(TVDBEpisode.id == ep_data.id.string).first()
                    if episode:
                        episode.update_from_bss(ep_data)
                    else:
                        episode = TVDBEpisode(ep_data)
                    series.episodes.append(episode)
                    session.merge(series)
        except URLError, e:
            raise LookupError('Error looking up episode from TVDb (%s)' % e)
    if episode:
        # Access the series attribute to force it to load before returning
        episode.series
        return episode
    else:
        raise LookupError('No results found for ')


@with_session
def mark_expired(session=None):
    """Marks series and episodes that have expired since we cached them"""
    # Only get the expired list every hour
    last_server = persist.get('last_server')
    last_local = persist.get('last_local')
    if not last_local or not last_server:
        last_server = ''
    elif last_local + timedelta(hours=1) > datetime.now():
        # It has been less than an hour, don't check again yet
        return

    try:
        # Get items that have changed since our last update
        updates = BeautifulStoneSoup(urlopener(server + 'Updates.php?type=all&time=%s' % last_server, log)).items
    except URLError, e:
        log.error('Could not get update information from tvdb: %s' % e)
        return
    if updates:
        # Make lists of expired series and episode ids
        expired_series = [int(series.string) for series in updates.findAll('series')]
        expired_episodes = [int(ep.string) for ep in updates.findAll('episode')]

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
        new_server = str(updates.find('time').string)
        persist['last_local'] = datetime.now()
        persist['last_server'] = new_server
