import urllib
import logging

log = logging.getLogger('ui.themoviedb')


class TMDB(object):

    def __init__(self, api_key='50f722dc90c43df28eced4a212a01f74', markup='yaml', lang='en'):
        '''
        TMDB Client
        '''
        self.lang = lang
        self.markup = markup
        self.key = api_key
        self.server = 'http://api.themoviedb.org'

    def connection(self, url):
        '''
        Return URL Content
        '''
        data = None
        try:
            client = urllib.urlopen(url)
            data = client.read()
            client.close()
        except Exception, e:
            log.debug('Connection failure: %s' % e)
        return data

    def build_url(self, look, term):
        '''
        Methods => search, imdbLookup, getInfo, getImages
        '''
        return '%s/2.1/Movie.%s/%s/%s/%s/%s' % (
            self.server, look, self.lang, self.markup, self.key, term)

    def search_results(self, term):
        '''
        Search Wrapper
        '''
        return self.connection(self.build_url('search', term))

    def get_info(self, tmdb_id):
        '''
        GetInfo Wrapper
        '''
        return self.connection(self.build_url('getInfo', tmdb_id))

    def imdb_results(self, imdb_id):
        '''
        IMDB Search Wrapper
        '''
        log.debug('Looking up imdb id: %s' % imdb_id)
        return self.connection(self.build_url('imdbLookup', imdb_id))

    def imdb_images(self, imdb_id):
        '''
        IMDB Search Wrapper
        '''
        imdb_id = 'tt0%s' % imdb_id
        return self.connection(self.build_url('getImages', imdb_id))

    def tmdb_images(self, tmdb_id):
        '''
        GetInfo Wrapper
        '''
        return self.connection(self.build_url('getImages', tmdb_id))
