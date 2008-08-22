import unittest
from manager import Manager
from feed import Feed, Entry

class FlexGetTestCase(unittest.TestCase):

    def setUp(self):
        """Set up test env"""
        if not hasattr(self, 'config'):
            self.fail('Config file missing')
        self.manager = Manager()
        self.manager.options.config = self.config
        # do not write session, note this will skip events DOWNLOAD and OUTPUT
        # will need to be re-thinked when those events are to be tested
        self.manager.options.test = True
        # do not load session
        self.manager.options.reset = True
        #self.manager.options.details = True
        self.manager.load_config()
        config = self.manager.config['feeds']['test']
        self.feed = Feed(self.manager, 'test', config)
        self.feed.unittest = True
        
    def getModule(self, event, keyword):
        module = self.manager.modules.get(keyword)
        if not module:
            raise Exception('module %s isn\'t loaded (event %s)' % (keyword, event))
        return module

class TestFilterSeries(FlexGetTestCase):

    def setUp(self):
        self.config = 'test/test_series.yml'
        FlexGetTestCase.setUp(self)
        self.feed.execute()

    def testSerieParser(self):
        from filter_series import SerieParser
        s1 = SerieParser()
        s1.name = 'Something Interesting'
        s1.data = 'Something.Interesting.S01E02-FlexGet'
        s1.parse()
        self.assertEqual(s1.season, 1)
        self.assertEqual(s1.episode, 2)
        self.assertEqual(s1.quality, 'unknown')


class TestPatterns(FlexGetTestCase):

    def setUp(self):
        self.config = 'test/test_patterns.yml'
        FlexGetTestCase.setUp(self)
        self.feed.execute()
        if not self.feed.entries:
            self.fail('no entries')
                
    def testPattern(self):
        module = self.getModule('filter', 'patterns')
        entry = self.feed.entries[0]
        self.assertEqual(entry['title'], 'pattern')
        self.assertEqual(entry['url'], 'http://localhost/pattern')
        
    def testAccept(self):
        module = self.getModule('filter', 'accept')
        entry = self.feed.entries[1]
        self.assertEqual(entry['title'], 'accept')
        self.assertEqual(entry['url'], 'http://localhost/accept')
        
    def testFiltered(self):
        entry = self.feed.filtered[0]
        self.assertEqual(entry['title'], 'unmatched')
        self.assertEqual(entry['url'], 'http://localhost/unmatched')
        
        
class TestResolvers(FlexGetTestCase):

    def setUp(self):
        self.config = 'test/test_resolvers.yml'
        FlexGetTestCase.setUp(self)
        self.feed.execute()
        
    def get_resolver(self, name):
        info = self.manager.get_module_by_name(name)
        return info['instance']
        
    def testPirateBay(self):
        # test with piratebay entry
        resolver = self.get_resolver('piratebay')
        entry = self.feed.entries[0]
        self.assertEqual(resolver.resolvable(self.feed, entry), True)

    def testPirateBaySearch(self):
        # test with piratebay entry
        resolver = self.get_resolver('piratebay')
        entry = self.feed.entries[1]
        self.assertEqual(resolver.resolvable(self.feed, entry), True)
        
        
    def testNyaaTorrents(self):
        entry = self.feed.entries[2]
        resolver = self.get_resolver('resolve_nyaatorrents')
        self.assertEqual(entry['url'], 'http://www.nyaatorrents.org/?page=torrentinfo&tid=12345')
        self.assertEqual(resolver.resolvable(self.feed, entry), True)
        resolver.resolve(self.feed, entry)
        self.assertEqual(entry['url'], 'http://www.nyaatorrents.org/?page=download&tid=12345')
    
    
if __name__ == '__main__':
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestPatterns))
    suite.addTest(unittest.makeSuite(TestResolvers))
    suite.addTest(unittest.makeSuite(TestFilterSeries))
    # run suite
    unittest.TextTestRunner(verbosity=2).run(suite)
