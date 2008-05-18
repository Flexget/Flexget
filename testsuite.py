import unittest
from manager import Manager
from feed import Feed, Entry

class TestPatterns(unittest.TestCase):

    def setUp(self):
        """Set up test env"""
        self.manager = Manager()
        self.manager.options.config = 'test/test_patterns.yml'
        self.manager.load_config()
        config = self.manager.config['feeds']['test']
        self.feed = Feed(self.manager, 'test', config)
                
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
    
    
if __name__ == '__main__':
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestPatterns))
    # run suite
    unittest.TextTestRunner(verbosity=2).run(suite)
