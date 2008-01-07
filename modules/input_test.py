__instance__ = "FeedTest"

class FeedTest:

    """ dummy module for testing, finds one dummy hit """

    def register(self, manager):
        manager.register(instance=self, type="input", keyword="test", callback=self.run, order=1, debug_module=True)

    def run(self, feed):
        for i in range(10):
            dummy = {}
            dummy['title'] = 'dummy title %i' % i
            dummy['url'] = 'http://127.0.0.1/dummy%i' %i
            dummy['imdb_score'] = 5.2
            dummy['imdb_votes'] = 1253
            feed.entries.append(dummy)
