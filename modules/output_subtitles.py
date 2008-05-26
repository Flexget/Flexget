from xmlrpclib import ServerProxy
import urllib2

# movie hash, won't work here though
# http://trac.opensubtitles.org/projects/opensubtitles/wiki/HashSourceCodes#Python

# xmlrpc spec
# http://trac.opensubtitles.org/projects/opensubtitles/wiki/XMLRPC

class Subtitles:
    """
    Fetch subtitles from opensubtitles.org
    """
    def __init__(self):
        pass

    def register(self, manager, parser):
        manager.register(event='terminate', keyword='subtitles', callback=self.get_subtitles)

    def get_subtitles(self, feed):

        # filter all entries that have IMDB ID set

        
        s = ServerProxy("http://www.opensubtitles.org/xml-rpc")
        
        res = s.LogIn("", "", "en", "flexget")

        if res['status'] != '200 OK':
            raise Exception("Login to opensubtitles.org XML-RPC interface failed")

        token = res['token']

        # loop through the entries
        

        # these go into config file
        languages = ['fin', 'swe', 'eng']
        min_sub_rating = 0.0
    

        query = []
        for language in languages:
            query.append({'sublanguageid': language, 'imdbid': imdbid})
            
        subtitles = s.SearchSubtitles(token, query)
        subtitles = subtitles['data']
        # filter bad subs
        subtitles = filter(lambda x: x['SubBad'] =='0', subtitles)
        # some quality required (0.0 == not reviewed)
        subtitles = filter(lambda x: float(x['SubRating']) >= min_sub_rating or float(x['SubRating']) == 0.0, subtitles)

        filtered_subs = []

        # find the best rated subs for each language
        for language in languages:
            langsubs = filter(lambda x: x['SubLanguageID'] == language, subtitles)
            # find the best one
            # magic!
            langsubs.sort(key=lambda x: float(x['SubRating']), reverse=True)
            
            filtered_subs.append(langsubs[0])


        # download
        for sub in filtered_subs:
            subfile = urllib2.urlopen(sub['SubDownloadLink']).read()
            # save somewhere?

        s.LogOut(token)
        

if __name__ == "__main__":
    pass
