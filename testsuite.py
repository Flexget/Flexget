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
        s = SerieParser()
        s.name = 'Something Interesting'
        s.data = 'Something.Interesting.S01E02-FlexGet'
        s.parse()
        self.assertEqual(s.season, 1)
        self.assertEqual(s.episode, 2)
        self.assertEqual(s.quality, 'unknown')

        s = SerieParser()
        s.name = 'Something Interesting'
        s.data = 'The.Something.Interesting.S01E02-FlexGet'
        s.parse()
        assert not s.valid, 'Should not be valid'

        s = SerieParser()
        s.name = '25'
        s.data = '25.And.More.S01E02-FlexGet'
        s.parse()
        # TODO: This behavior should be changed.
        assert s.valid, 'Fix the implementation, should not be valid'

        # test invalid name
        s = SerieParser()
        s.name = 1
        s.data = 'Something'
        try:
            s.parse()
        except:
            pass
        else:
            fail('Data was not a str, should have failed')
        
        # test invalid data
        s = SerieParser()
        s.name = 'Something Interesting'
        s.data = 1
        try:
            s.parse()
        except:
            pass
        else:
            fail('Data was not a str, should have failed')
            
    def testSeries(self):
        # another series should be accepted
        e = self.feed.entries[0]
        self.assertEqual(e['title'], 'Another.Series.S01E20.720p.XViD-FlexGet')
        # some series should be in timeframe-queue
        self.feed.shared_cache.set_namespace('series')
        s = self.feed.shared_cache.get('some series')
        self.assertEqual(isinstance(s, dict), True)
        self.assertEqual(s.get('S1E20', {}).get('info').get('downloaded'), False)


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
        entry = self.feed.entries[2]
        self.assertEqual(entry['title'], 'xxx.yyyy')
        
    def testFiltered(self):
        entry = self.feed.filtered[0]
        self.assertEqual(entry['title'], 'unmatched')
        self.assertEqual(entry['url'], 'http://localhost/unmatched')
        
    def testNot(self):
        entry = self.feed.filtered[1]
        self.assertEqual(entry['title'], 'foobar')
        
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
        
        
class TestManager(FlexGetTestCase):

    def setUp(self):
        # just load with some conf
        self.config = 'test/test_patterns.yml'
        FlexGetTestCase.setUp(self)
        
    def testFailed(self):
        e = Entry()
        e['title'] = 'test'
        e['url'] = 'http://localhost/mock'
        self.manager.add_failed(e)
        assert len(self.manager.session['failed']) == 1, 'failed to add'
        e = Entry()
        e['title'] = 'test 2'
        e['url'] = 'http://localhost/mock'
        self.manager.add_failed(e)
        assert len(self.manager.session['failed']) == 2, 'failed to add again'
        self.manager.add_failed(e)
        assert len(self.manager.session['failed']) == 2, 'failed to filter already added'

class TestCache(unittest.TestCase):

    def setUp(self):
        from feed import ModuleCache
        self.master = {}
        self.cache = ModuleCache('test', self.master)
        
    def testNamespace(self):
        self.cache.set_namespace('namespace')
        assert self.cache.get_namespace() == 'namespace', 'cache namespace is not correct'
        
    def testStoreDefault(self):
        self.cache.set_namespace('storedefault')
        dummy = object()
        ret = self.cache.storedefault('name', dummy, days=69)
        if not ret is dummy:
            self.fail('store_default return is not correct')
        assert self.cache._cache.get('name', {}).get('days', None) == 69, 'stored days not correct'
        assert self.cache.get('name') == dummy, 'get failed'
        ret = self.cache.storedefault('name', 'value')
        assert ret == dummy, 'store existing failed'
        
    def testStore(self):
        self.cache.set_namespace('store')
        self.cache.store('foo', 'bar')
        assert self.cache.get('foo') == 'bar', 'get failed'
        self.cache.store('foo', 'xxx')
        assert self.cache.get('foo') == 'xxx', 'overwrite failed'
        self.cache.remove('foo')
        dummy = object()
        ret = self.cache.get('foo', dummy)
        assert ret == dummy, 'remove failed'       

    
    
if __name__ == '__main__':
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestPatterns))
    suite.addTest(unittest.makeSuite(TestResolvers))
    suite.addTest(unittest.makeSuite(TestFilterSeries))
    suite.addTest(unittest.makeSuite(TestManager))
    suite.addTest(unittest.makeSuite(TestCache))
    # run suite
    unittest.TextTestRunner(verbosity=2).run(suite)
