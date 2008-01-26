import random

class FeedTest:

    ''' dummy module for testing '''

    def register(self, manager, parser):
        manager.register(instance=self, type='input', keyword='input_test', callback=self.run, order=1, debug_module=True)

    def run(self, feed):
        for i in range(10):
            dummy = {}
            dummy['title'] = 'dummy title %i' % i
            dummy['url'] = 'http://127.0.0.1/dummy%i' %i
            dummy['imdb_score'] = 5.2
            dummy['imdb_votes'] = 1253
            dummy['instance'] = object()
            feed.entries.append(dummy)

        # add serie entries
        for ep in ['S1E01', 'S1E02', 'S1E03']:
            q = ['DSR','HR','720p', '1080p', 'HDTV']
            dummy = {}
            dummy['title'] = 'Mock.Serie.%s.%s.ByN00B-XviD.avi' % (ep, random.choice(q))
            dummy['url'] = 'http://127.0.0.1/%s' % dummy['title']
            feed.entries.append(dummy)
            
