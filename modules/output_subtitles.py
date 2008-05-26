import xmlrpclib

class Subtitles:
    """
    Fetch subtitles from opensubtitles.org
    """
    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failed = 0

    def register(self, manager, parser):
##         manager.register(event='input', keyword='statistics', callback=self.input, order=65535)
##         manager.register(event='exit', keyword='statistics', callback=self.exit)
##         manager.register(event='terminate', keyword='statistics', callback=self.generate_statistics)

    def fetch(self, feed):
        s = ServerProxy("http://www.opensubtitles.org/xml-rpc")
        res = s.LogIn("", "", "en", "flexget")
        imdbid = "123456"
        languages = ['fin', 'swe']

        query = []
        for language in languages:
            query.append({'sublanguageid': langid, 'imdbid': imdbid})
            
        subtitles = s.SearchSubtitles(res['token'], query)

        for subtitle in subtitles['data']:
            subtitle['SubDownloadLink']
            subtitle['SubRating']
            subtitle['SubBad']
        

if __name__ == "__main__":
    pass
