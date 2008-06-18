from xmlrpclib import ServerProxy
import urllib2
import re
import difflib
import os.path
import sys
import types

# movie hash, won't work here though
# http://trac.opensubtitles.org/projects/opensubtitles/wiki/HashSourceCodes#Python

# xmlrpc spec
# http://trac.opensubtitles.org/projects/opensubtitles/wiki/XMLRPC

class Subtitles:
    """
    Fetch subtitles from opensubtitles.org
    """

    def register(self, manager, parser):
        manager.register(event='output', keyword='subtitles', callback=self.get_subtitles)

    def get_config(self, feed):
        config = feed.config['subtitles']
        if type(config) != types.DictType:
            config = {}

        config.setdefault('output', os.path.join(sys.path[0]))
        config.setdefault('languages', ['eng'])
        config.setdefault('min_sub_rating', 0.0)
        config.setdefault('match_limit', 0.8)

        config['output'] = os.path.expanduser(config['output'])
            
        return config

    def get_subtitles(self, feed):

        # filter all entries that have IMDB ID set
        try:
            entries = filter(lambda x: x['imdb_url'] != None, feed.entries)
        except KeyError:
            # No imdb urls on this feed, skip it
            return

        s = ServerProxy("http://www.opensubtitles.org/xml-rpc")
        
        res = s.LogIn("", "", "en", "Flexget")

        if res['status'] != '200 OK':
            raise Exception("Login to opensubtitles.org XML-RPC interface failed")

        config = self.get_config(feed)

        token = res['token']

        # these go into config file
        languages = config['languages']
        min_sub_rating = config['min_sub_rating']
        match_limit = config['match_limit'] # no need to change this, but it should be configurable
        
        # loop through the entries
        for entry in entries:            
            # dig out the raw imdb id 
            m = re.search("tt(\d+)/$", entry['imdb_url'])
            if not m:
                print "no match for "+entry['imdb_url']
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
                        langsubs.sort(key=lambda x: float(x['SubRating']), reverse=True)
                        filtered_subs.append(langsubs[0])

            # download
            for sub in filtered_subs:
                #print sub
                #print "SUBS FOUND: ", sub['MovieReleaseName'], sub['SubRating'], sub['SubLanguageID']

                f = urllib2.urlopen(sub['ZipDownloadLink'])
                subfilename = re.match('^attachment; filename="(.*)"$', f.info()['content-disposition']).group(1)
                outfile = os.path.join(config['output'], subfilename)
                fp = file(outfile, 'w')
                fp.write(f.read())
                fp.close()
                f.close()

        s.LogOut(token)
        

if __name__ == "__main__":
    pass
