from xmlrpclib import ServerProxy
import urllib2
import re
import difflib
import os.path
import sys
import logging

from flexget.manager import Session, Base
from sqlalchemy import Column, Integer, String, DateTime, PickleType
from datetime import datetime, timedelta

""" 

DRAFT

class SubtitleQueue(Base):
    
    __tablename__ = 'subtitle_queue'

    id = Column(Integer, primary_key=True)
    feed = Column(String)
    imdb_id = Column(String)
    added = Column(DateTime)
    
    def __init__(self, feed, imdb_id):
        self.feed = feed
        self.imdb_id = imdb_id
        self.added = datetime.now()
    
    def __str__(self):
        return '<SubtitleQueue(%s=%s)>' % (self.feed, self.imdb_id)
        
TODO:
 
 * add new option, retry: [n] days
 * add everything into queue using above class
 * consume queue (look up by feed name), configuration is available from feed
 * remove successful downloads
 * remove queue items that are part retry: n days 
        
"""        

log = logging.getLogger('subtitles')

# movie hash, won't work here though
# http://trac.opensubtitles.org/projects/opensubtitles/wiki/HashSourceCodes#Python

# xmlrpc spec
# http://trac.opensubtitles.org/projects/opensubtitles/wiki/XMLRPC

class Subtitles:
    
    """
    Fetch subtitles from opensubtitles.org
    """

    __plugin__ = 'subtitles'

    def validator(self):
        from flexget import validator
        subs = validator.factory('dict')
        langs = subs.accept('list', key='languages')
        langs.accept('text')
        subs.accept('decimal', key='min_sub_rating')
        subs.accept('decimal', key='match_limit')
        return subs
        
    def get_config(self, feed):
        config = feed.config['subtitles']
        if not isinstance(config, dict):
            config = {}
        config.setdefault('output', feed.manager.config_base)
        config.setdefault('languages', ['eng'])
        config.setdefault('min_sub_rating', 0.0)
        config.setdefault('match_limit', 0.8)
        config['output'] = os.path.expanduser(config['output'])
        return config

    def feed_download(self, feed):

        # filter all entries that have IMDB ID set
        try:
            entries = filter(lambda x: x['imdb_url'] != None, feed.accepted)
        except KeyError:
            # No imdb urls on this feed, skip it
            return


        try:
            s = ServerProxy("http://www.opensubtitles.org/xml-rpc")
            res = s.LogIn("", "", "en", "FlexGet")
        except:
            log.warning('Error connecting to opensubtitles.org')
            return

        if res['status'] != '200 OK':
            raise Exception("Login to opensubtitles.org XML-RPC interface failed")

        config = self.get_config(feed)

        token = res['token']

        # configuration
        languages = config['languages']
        min_sub_rating = config['min_sub_rating']
        match_limit = config['match_limit'] # no need to change this, but it should be configurable
        
        # loop through the entries
        for entry in entries:            
            # dig out the raw imdb id 
            m = re.search("tt(\d+)/$", entry['imdb_url'])
            if not m:
                log.debug("no match for "+entry['imdb_url'])
                continue

            imdbid = m.group(1)
            
            query = []
            for language in languages:
                query.append({'sublanguageid': language, 'imdbid': imdbid})
            
            subtitles = s.SearchSubtitles(token, query)
            subtitles = subtitles['data']

            # nothing found -> continue
            if not subtitles: continue
            
            # filter bad subs
            subtitles = filter(lambda x: x['SubBad'] == '0', subtitles)
            # some quality required (0.0 == not reviewed)
            subtitles = filter(lambda x: float(x['SubRating']) >= min_sub_rating or float(x['SubRating']) == 0.0, subtitles)

            filtered_subs = []

            # find the best rated subs for each language
            for language in languages:
                langsubs = filter(lambda x: x['SubLanguageID'] == language, subtitles)

                # did we find any subs for this language?
                if langsubs:

                    def seqmatch(subfile):
                        s = difflib.SequenceMatcher(lambda x: x in " ._", entry['title'], subfile)
                        #print "matching: ", entry['title'], subfile, s.ratio()
                        return s.ratio() > match_limit

                    # filter only those that have matching release names
                    langsubs = filter(lambda x: seqmatch(x['MovieReleaseName']), subtitles)

                    if langsubs:
                        # find the best one by SubRating
                        langsubs.sort(key=lambda x: float(x['SubRating']))
                        langsubs.reverse()
                        filtered_subs.append(langsubs[0])

            # download
            for sub in filtered_subs:
                log.debug('SUBS FOUND: ', sub['MovieReleaseName'], sub['SubRating'], sub['SubLanguageID'])

                f = urllib2.urlopen(sub['ZipDownloadLink'])
                subfilename = re.match('^attachment; filename="(.*)"$', f.info()['content-disposition']).group(1)
                outfile = os.path.join(config['output'], subfilename)
                fp = file(outfile, 'w')
                fp.write(f.read())
                fp.close()
                f.close()

        s.LogOut(token)     
