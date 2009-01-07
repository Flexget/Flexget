import os, unittest
from manager import Manager
from feed import Feed, Entry

class FlexGetTestCase(unittest.TestCase):

    def setUp(self):
        """Set up test env"""
        if not hasattr(self, 'config'):
            self.fail('Config file missing')
        self.manager = Manager()
        self.manager.options.config = self.config
        # do not load session
        self.manager.options.reset = True
        self.manager.initialize()
        # test feed for easy access
        config = self.manager.config['feeds']['test']
        self.feed = Feed(self.manager, 'test', config)
        self.feed.unittest = True
        
    def tearDown(self):
        self.manager.save_session()
        os.remove(self.manager.session_name)
        
    def getModule(self, event, keyword):
        module = self.manager.modules.get(keyword)
        if not module:
            raise Exception('module %s isn\'t loaded (event %s)' % (keyword, event))
        return module
        
    def get_entry(self, **values):
        """Get entry from feed with given parameters"""
        for entry in self.feed.entries:
            match = 0
            for k, v in values.iteritems():
                if entry.has_key(k):
                    if entry.get(k) == v: 
                        match += 1
            if match==len(values):
                return entry
        return None
    

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
            self.fail('Data was not a str, should have failed')
        
        # test invalid data
        s = SerieParser()
        s.name = 'Something Interesting'
        s.data = 1
        try:
            s.parse()
        except:
            pass
        else:
            self.fail('Data was not a str, should have failed')
            
    def testSeries(self):
        # 'some series' should be in timeframe-queue
        self.feed.shared_cache.set_namespace('series')
        s = self.feed.shared_cache.get('some series')
        self.assertEqual(isinstance(s, dict), True)
        self.assertEqual(s.get('S1E20', {}).get('info').get('downloaded'), False)
        
        # normal passing
        if not self.get_entry(title='Another.Series.S01E20.720p.XViD-FlexGet'):
            self.fail('Another.Series.S01E20.720p.XViD-FlexGet should have passed')
        # episode advancement
        if self.get_entry(title='Another.Series.S01E10.720p.XViD-FlexGet'):
            self.fail('Another.Series.S01E10.720p.XViD-FlexGet should NOT have passed because of episode advancement')
        if not self.get_entry(title='Another.Series.S01E16.720p.XViD-FlexGet'):
            self.fail('Another.Series.S01E16.720p.XViD-FlexGet should have passed because of episode advancement grace magin')
        # date formats
        df = ['Date.Series.10-11-2008.XViD','Date.Series.10.12.2008.XViD','Date.Series.2008-10-13.XViD','Date.Series.2008x10.14.XViD']
        for d in df:
            if not self.get_entry(title=d):
                self.fail('Date format did not match %s' % d)


class TestPatterns(FlexGetTestCase):

    def setUp(self):
        self.config = 'test/test_patterns.yml'
        FlexGetTestCase.setUp(self)
        self.feed.execute()
        if not self.feed.entries:
            self.fail('no entries')
                
    def testPattern(self):
        #module = self.getModule('filter', 'patterns')
        entry = self.feed.entries[0]
        self.assertEqual(entry['title'], 'pattern')
        self.assertEqual(entry['url'], 'http://localhost/pattern')
        
    def testAccept(self):
        #module = self.getModule('filter', 'accept')
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

class TestDownload(FlexGetTestCase):

    def setUp(self):
        self.config = 'test/test_download.yml'
        FlexGetTestCase.setUp(self)

    def testDownload(self):
        self.testfile = os.path.expanduser('~/flexget_test')
        if os.path.exists(self.testfile):
            os.remove(self.testfile)
        # executes feed and downloads the file
        self.feed.execute()
        if not os.path.exists(self.testfile):
            self.fail('download file does not exists')
        else:
            os.remove(self.testfile)

class TestInputRSS(FlexGetTestCase):

    def setUp(self):
        self.config = 'test/test_rss.yml'
        FlexGetTestCase.setUp(self)

    def testInputRSS(self):
        self.feed.execute()
        
        # normal entry
        if not self.get_entry(title='Normal', url='http://localhost/normal', description='Description, normal'):
            self.fail('RSS entry missing: normal')
        
        # multiple enclosures
        if not self.get_entry(title='Multiple enclosures', url='http://localhost/enclosure1', filename='enclosure1', description='Description, multiple'):
            self.fail('RSS entry missing: enclosure1')
        if not self.get_entry(title='Multiple enclosures', url='http://localhost/enclosure2', filename='enclosure2', description='Description, multiple'):
            self.fail('RSS entry missing: enclosure2')
        if not self.get_entry(title='Multiple enclosures', url='http://localhost/enclosure3', filename='enclosure3', description='Description, multiple'):
            self.fail('RSS entry missing: enclosure3')
        
        # zero sized enclosure should not pick up filename (some idiotic sites)
        e = self.get_entry(title='Zero sized enclosure')
        if not e:
            self.fail('RSS entry missing: zero sized')
        if e.has_key('filename'):
            self.fail('RSS entry with 0-sized enclosure should not have explicit filename')
        
        # messy enclosure
        e = self.get_entry(title='Messy enclosure')
        if not e:
            self.fail('RSS entry missing: messy')
        if not e.has_key('filename'):
            self.fail('Messy RSS enclosure: missing filename')
        if e['filename'] != 'enclosure.mp3':
            self.fail('Messy RSS enclosure: wrong filename')
        
        # pick link from guid
        if not self.get_entry(title='Guid link', url='http://localhost/guid', description='Description, guid'):
            self.fail('RSS entry missing: guid')
            
        # empty title, should be skipped
        if self.get_entry(description='Description, empty title'):
            self.fail('RSS entry without title should be skipped')
        
    
if __name__ == '__main__':
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestPatterns))
    suite.addTest(unittest.makeSuite(TestResolvers))
    suite.addTest(unittest.makeSuite(TestFilterSeries))
    suite.addTest(unittest.makeSuite(TestManager))
    suite.addTest(unittest.makeSuite(TestCache))
    suite.addTest(unittest.makeSuite(TestDownload))
    suite.addTest(unittest.makeSuite(TestInputRSS))
    # run suite
    unittest.TextTestRunner(verbosity=2).run(suite)
