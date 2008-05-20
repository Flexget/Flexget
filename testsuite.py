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
        self.manager.load_config()
        config = self.manager.config['feeds']['test']
        self.feed = Feed(self.manager, 'test', config)
        self.feed.unittest = True


class TestPatterns(FlexGetTestCase):

    def setUp(self):
        self.config = 'test/test_patterns.yml'
        FlexGetTestCase.setUp(self)
                
    def testPattern(self):
        module = self.manager.modules['filter'].get('patterns')
        if not module:
            self.fail('patterns module not loaded')
        self.feed.execute()
        if not self.feed.entries:
            self.fail('no entries')
        entry = self.feed.entries[0]
        self.assertEqual(entry['title'], 'something')
        self.assertEqual(entry['url'], 'http://localhost/asdf')
        
        
class TestResolvers(FlexGetTestCase):

    def setUp(self):
        self.config = 'test/test_resolvers.yml'
        FlexGetTestCase.setUp(self)
        
    def testPirateBay(self):
        self.feed.execute()
        # test with piratebay entry
        entry = self.feed.entries[0]
        self.assertEqual(self.feed.resolvable(entry), True)
        # not a piratebay entry
        entry = self.feed.entries[1]
        self.assertEqual(self.feed.resolvable(entry), False)

    
    
if __name__ == '__main__':
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestPatterns))
    suite.addTest(unittest.makeSuite(TestResolvers))
    # run suite
    unittest.TextTestRunner(verbosity=2).run(suite)
