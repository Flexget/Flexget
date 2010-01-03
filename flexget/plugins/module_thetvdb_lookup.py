import logging
from flexget.plugin import *
from flexget.manager import Base, Session
from sqlalchemy import Column, Integer, Unicode, UnicodeText, DateTime
from BeautifulSoup import BeautifulStoneSoup
import urllib
import datetime

log = logging.getLogger('thetvdb')


class TheTvDB(Base):
    
    __tablename__ = 'thetvdb'

    id = Column(Integer, primary_key=True)
    series_name = Column(Unicode)
    series_xml = Column(UnicodeText)
    added = Column(DateTime)
    
    def __init__(self, series_name, series_xml):
        self.series_name = series_name
        self.series_xml = series_xml
        self.added = datetime.datetime.now()
    
    def __str__(self):
        return '<Thetvdb(%s=%s)>' % (self.series_name, self.series_xml)


class ModuleThetvdbLookup:
    """
        Retrieves TheTVDB information for entries. Uses series_name, 
        series_season, series_episode from series plugin.
        
        NOTE: This MUST be executed after series! Thus, priority of
        any script that uses this needs to be filter priority < 128
        (that's the priority of series)

        Example:

        thetvdb_lookup: yes
        
        Primarily used for passing thetvdb information to other plugins.
        Among these is the IMDB url for the series.
        
        This information is provided (via entry):
          series info:
            series_name_thetvdb
            series_rating
            series_status (Continuing or Ended)
            series_runtime (show runtime in minutes)
            series_first_air_date
            series_air_time
            series_content_rating
            series_genres
            series_network
            series_banner_url
            series_fanart_url
            series_poster_url
            series_airs_day_of_week
            series_actors
            series_language (en, fr, etc.)
            imdb_url (if available)
            zap2it_id (if available)
          episode info: (if episode is found)
            ep_name
            ep_overview
            ep_director
            ep_writer
            ep_air_date
            ep_rating
            ep_guest_stars
            ep_image_url
    """
        
    def validator(self):
        from flexget import validator
        return validator.factory('boolean')

    def on_feed_filter(self, feed):
        from flexget.utils.log import log_once
        for entry in feed.entries:
            try:
                self.lookup(feed, entry)
            except PluginError, e:
                log_once(e.value.capitalize(), logger=log)
            except PluginWarning, e:
                log_once(e.value.capitalize(), logger=log)
    
    def _convert_date(self, date_to_convert):
        """ 
        Take in a date in this format:
        1986-12-17
        and spit out a datetime object
        """
        converted_date = None
        try:
            converted_date = datetime.date(*map(int, date_to_convert.split("-")))
        except ValueError:
            pass

        return converted_date
    
    def lookup(self, feed, entry):
        """
        Get theTVDB information for the included series_name,
        series_season, series_episode.
        """
        # Search for series (need to get latest first_airing_date for default)
        # http://thetvdb.com/api/GetSeries.php?seriesname=Castle
        # Castle (2009)'s URL:
        # http://thetvdb.com/data/series/83462/
        # Castle (2009) all episode information:
        # http://thetvdb.com/data/series/83462/all/
        # Images are base url:
        # http://thetvdb.com/banners/
        
        log.debug("looking up %s" % entry['title'])
        
        # Check to make sure that I have all info I need before I start.
        if not 'series_name' in entry:
            # TODO: try to apply regexes to this to figure out series name, season and ep number from title.
            log.debug("series_name not given for %s. Entry not parsed through series plugin" % entry["title"])
            return
        if not 'series_season' in entry:
            log.warning("failed getting series_season for %s, but given series_name. Series plugin bug?" % entry["series_name"])
            raise PluginError('TheTVDB Lookup fails due to missing series_season')
        if not 'series_episode' in entry:
            log.warning("failed getting series_episode for %s, but given series_name. Series plugin bug?" % entry["series_name"])
            raise PluginError('TheTVDB Lookup fails due to missing series_episode')
        
        log.debug("Retrieved internal series info for %(series_name)s - S%(series_season)sE%(series_episode)s" % entry)
        
        session = Session()
        
        # if I can't pull the series info from the DB:
        seriesdata = session.query(TheTvDB).filter(TheTvDB.series_name == unicode(entry['series_name'])).first()
        if not seriesdata:
            get_new_info = True
        # otherwise, if it's more than an hour old...
        elif seriesdata.added < datetime.datetime.now() - datetime.timedelta(hours=1):
            get_new_info = True
        else:
            get_new_info = False
        
        if get_new_info:
            feed.verbose_progress('Requesting %s information from TheTvDB.com' % entry['series_name'])
            # get my series data.
            # TODO: need to impliment error handling around grabbing url.
            seriesdata = BeautifulStoneSoup(urllib.urlopen("http://thetvdb.com/api/GetSeries.php?seriesname=%s" % entry["series_name"])).data
            # Yeah, I'm lazy. Grabbing the one with the latest airing date, 
            # instead of trying to see what's the closest match.
            # If there's an exact match, return that immediately. Could
            # run into issues with queries with multiple exact matches.
            newest_series_first_aired = datetime.date(1800, 1, 1)
            series_id = None
            for i in seriesdata.findAll("series", recursive=False):
                this_series_air_date = self._convert_date(i.firstaired.string)
                if this_series_air_date > newest_series_first_aired:
                    newest_series_first_aired = this_series_air_date
                    series_id = i.seriesid.string
                if i.seriesname.string == entry['series_name']:
                    series_id = i.seriesid.string
                    # Don't really need to store this, but just for consistancies sake so we always have it available
                    newest_series_first_aired = this_series_air_date
                    break
            if series_id == None:
                log.warning("Didn't get a return from tvdb on the series search for " % entry["series_name"])
                raise PluginWarning('No return on series lookup')
            
            # Grab the url, and parse it out into BSS. Store it's root element as data.
            # TODO: need to impliment error handling around grabbing url.
            data = BeautifulStoneSoup(urllib.urlopen("http://thetvdb.com/data/series/%s/all/" % str(series_id))).data
            session.add(TheTvDB(unicode(entry['series_name']), unicode(data)))
            
        else:
            data = BeautifulStoneSoup(session.query(TheTvDB).filter(TheTvDB.series_name == unicode(entry['series_name'])).first().series_xml).data
        
        session.commit()
        
        entry['series_name_tvdb'] = data.series.seriesname.string
        entry['series_rating'] = data.series.rating.string
        entry['series_status'] = data.series.status.string
        entry['series_runtime'] = data.series.runtime.string
        entry['series_first_air_date'] = self._convert_date(data.series.firstaired.string)
        entry['series_air_time'] = data.series.airs_time.string
        entry['series_content_rating'] = data.series.contentrating.string
        entry['series_genres'] = data.series.genre.string.strip("|").split("|")
        entry['series_network'] = data.series.network.string
        entry['series_banner_url'] = "http://www.thetvdb.com/banners/%s" % data.series.banner.string
        entry['series_fanart_url'] = "http://www.thetvdb.com/banners/%s" % data.series.fanart.string
        entry['series_poster_url'] = "http://www.thetvdb.com/banners/%s" % data.series.poster.string
        entry['series_airs_day_of_week'] = data.series.airs_dayofweek.string
        entry['series_actors'] = data.series.actors.string.strip("|").split("|")
        entry['series_language'] = data.series.language.string
        if data.series.imdb_id.string:
            entry["imdb_url"] = "http://www.imdb.com/title/%s" % data.series.imdb_id.string
        if data.series.zap2it_id.string:
            entry['zap2it_id'] = data.series.zap2it_id.string
        
        log.debug("searching for correct episode %(series_name)s - S%(series_season)sE%(series_episode)s on thetvdb" % entry)
        
        for i in data.findAll("episode", recursive=False):
            #print "%s %s %s %s" % (i.combined_season.string, i.episodenumber.string, entry['series_season'], entry['series_episode'])
            if int(i.combined_season.string) == int(entry['series_season']):
                if int(i.episodenumber.string) == int(entry['series_episode']):
                    entry['ep_name'] = i.episodename.string
                    log.debug("found episode: %(series_name)s - S%(series_season)sE%(series_episode)s - %(ep_name)s" % entry)
                    entry['ep_director'] = i.director.string
                    entry['ep_writer'] = i.writer.string
                    entry['ep_air_date'] = self._convert_date(i.firstaired.string)
                    entry['ep_rating'] = i.rating.string
                    entry['ep_image_url'] = "http://www.thetvdb.com/banners/%s" % i.filename.string
                    entry['ep_overview'] = i.overview.string
                    if i.gueststars.string:
                        entry['ep_guest_stars'] = i.gueststars.string.strip("|").split("|")
                    else:
                        entry['ep_guest_stars'] = []
        
        # If I didn't get a valid episode out of all that, log a debug message.
        if not 'ep_name' in entry:
            log.info("Didn't find an episode on thetvdb for %(series_name)s - S%(series_season)sE%(series_episode)s" % entry)

register_plugin(ModuleThetvdbLookup, 'thetvdb_lookup', priorities={'filter': 100})
