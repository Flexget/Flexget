#!/usr/bin/python

import os, sys, unittest
from flexget.manager import Manager, Session
from flexget.feed import Feed
from flexget import validator

class FlexGetTestCase(unittest.TestCase):

    def setUp(self):
        """Set up test env"""
        if not hasattr(self, 'config'):
            self.fail('Config file missing')
        self.manager = Manager(unit_test=True)
        self.manager.options.config = self.config # pylint: disable-msg=E1101
        # do not load session
        self.manager.options.reset = True
        self.manager.initialize()
        
    def tearDown(self):
        try:
            self.feed.session.close()
        except:
            pass
        fn = 'db-%s.sqlite' % self.manager.configname
        if os.path.exists(fn):
            os.remove(fn)

    def execute_feed(self, name):
        """Use to execute one test feed from config"""
        config = self.manager.config['feeds'][name]
        if hasattr(self, 'feed'):
            if hasattr(self, 'session'):
                self.feed.session.close() # pylint: disable-msg=E0203
        self.feed = Feed(self.manager, name, config)
        self.feed.session = Session()
        self.feed.process_start()
        self.feed.execute()
        self.feed.process_end()
        
    def get_plugin(self, event, keyword):
        plugin = self.manager.plugins.get(keyword)
        if not plugin:
            raise Exception('plugin %s isn\'t loaded (event %s)' % (keyword, event))
        return plugin

    def dump(self):
        """Helper method for debugging"""
        print 'entries=%s' % self.feed.entries
        print 'accepted=%s' % self.feed.accepted
        print 'rejected=%s' % self.feed.rejected

class TestFilterSeries(FlexGetTestCase):

    def setUp(self):
        self.config = 'test/series.yml'
        FlexGetTestCase.setUp(self)
        self.execute_feed('test')

    def testSeriesParser(self):
        from flexget.utils.series import SeriesParser
        
        s = SeriesParser()
        s.name = 'Something Interesting'
        s.data = 'Something.Interesting.S01E02.Proper-FlexGet'
        s.parse()
        self.assertEqual(s.season, 1)
        self.assertEqual(s.episode, 2)
        self.assertEqual(s.quality, 'unknown')
        assert not s.proper_or_repack, 'did not detect proper'
        

        s = SeriesParser()
        s.name = 'Something Interesting'
        s.data = 'The.Something.Interesting.S01E02-FlexGet'
        s.parse()
        assert not s.valid, 'Should not be valid'

        s = SeriesParser()
        s.name = '25'
        s.data = '25.And.More.S01E02-FlexGet'
        s.parse()
        # TODO: This behavior should be changed. uhh, why?
        assert s.valid, 'Fix the implementation, should not be valid'

        # test invalid name
        s = SeriesParser()
        s.name = 1
        s.data = 'Something'
        try:
            s.parse()
        except:
            pass
        else:
            self.fail('Data was not a str, should have failed')

        # test confusing format
        s = SeriesParser()
        s.name = 'Something'
        s.data = 'Something.2008x12.13-FlexGet'
        s.parse()
        assert not s.episode, 'Should not have episode'
        assert not s.season, 'Should not have season'
        assert s.id == '2008-12-13', 'invalid id'
        assert s.valid, 'should not valid'
        
        # test 01x02 format
        s = SeriesParser()
        s.name = 'Something'
        s.data = 'Something.01x02-FlexGet'
        s.parse()
        if not s.season==1 and s.episode==2:
            self.fail('failed to parse 01x02')
        
        # test invalid data
        s = SeriesParser()
        s.name = 'Something Interesting'
        s.data = 1
        try:
            s.parse()
        except:
            pass
        else:
            self.fail('Data was not a str, should have failed')
            
    def testSeries(self):
        # TODO: needs to be fixed after series is converted into SQLAlchemy
        """
        # 'some series' should be in timeframe-queue
        self.feed.shared_cache.set_namespace('series')
        s = self.feed.shared_cache.get('some series')
        self.assertEqual(isinstance(s, dict), True)
        self.assertEqual(s.get('S1E20', {}).get('info').get('downloaded'), False)
        """
        
        # normal passing
        if not self.feed.find_entry(title='Another.Series.S01E20.720p.XViD-FlexGet'):
            self.fail('Another.Series.S01E20.720p.XViD-FlexGet should have passed')
        # episode advancement
        if self.feed.find_entry('rejected', title='Another.Series.S01E10.720p.XViD-FlexGet'):
            self.fail('Another.Series.S01E10.720p.XViD-FlexGet should NOT have passed because of episode advancement')
        if not self.feed.find_entry('accepted', title='Another.Series.S01E16.720p.XViD-FlexGet'):
            self.fail('Another.Series.S01E16.720p.XViD-FlexGet should have passed because of episode advancement grace magin')
        # date formats
        df = ['Date.Series.10-11-2008.XViD','Date.Series.10.12.2008.XViD', 'Date.Series.2008-10-13.XViD', 'Date.Series.2008x10.14.XViD']
        for d in df:
            if not self.feed.find_entry(title=d):
                self.fail('Date format did not match %s' % d)
        # parse from filename
        if not self.feed.find_entry(filename='Filename.Series.S01E26.XViD'):
            self.fail('Filename parsing failed')
        # empty description
        if not self.feed.find_entry(title='Empty.Description.S01E22.XViD'):
            self.fail('Empty Description failed')

class TestRegexp(FlexGetTestCase):

    def setUp(self):
        self.config = 'test/regexp.yml'
        FlexGetTestCase.setUp(self)

    def testAccept(self):
        self.execute_feed('test_accept')
        if not self.feed.find_entry('accepted', title='regexp1'):
            self.fail('regexp1 should have been accepted')
        if not self.feed.find_entry('accepted', title='regexp2'):
            self.fail('regexp2 should have been accepted')
        if not self.feed.find_entry('accepted', title='regexp3'):
            self.fail('regexp3 should have been accepted')
        if not self.feed.find_entry('entries', title='regexp4'):
            self.fail('regexp4 should have been left')
        if not self.feed.find_entry('accepted', title='regexp2', path='~/custom_path/2/'):
            self.fail('regexp2 should have been accepter with custom path')
        if not self.feed.find_entry('accepted', title='regexp3', path='~/custom_path/3/'):
            self.fail('regexp3 should have been accepter with custom path')
            
    def testReject(self):
        self.execute_feed('test_reject')
        if not self.feed.find_entry('rejected', title='regexp1'):
            self.fail('regexp1 should have been rejected')

    def testRest(self):
        self.execute_feed('test_rest')
        if not self.feed.find_entry('accepted', title='regexp1'):
            self.fail('regexp1 should have been accepted')
        if not self.feed.find_entry('rejected', title='regexp3'):
            self.fail('regexp3 should have been rejected')
            
    def testExcluding(self):
        self.execute_feed('test_excluding')
        if self.feed.find_entry('accepted', title='regexp1'):
            self.fail('regexp1 should not have been accepted')
        if not self.feed.find_entry('accepted', title='regexp2'):
            self.fail('regexp2 should have been accepted')
        if not self.feed.find_entry('accepted', title='regexp3'):
            self.fail('regexp3 should have been accepted')

    def testFrom(self):
        self.execute_feed('test_from')
        if self.feed.accepted:
            self.fail('should not have accepted anything')
        
class TestResolvers(FlexGetTestCase):

    """
        Bad example, does things manually, you should use feed.find_entry to check existance
    """

    def setUp(self):
        self.config = 'test/resolvers.yml'
        FlexGetTestCase.setUp(self)
        self.execute_feed('test')
        
    def get_resolver(self, name):
        info = self.manager.get_plugin_by_name(name)
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
        resolver = self.get_resolver('nyaatorrents')
        self.assertEqual(entry['url'], 'http://www.nyaatorrents.org/?page=torrentinfo&tid=12345')
        self.assertEqual(resolver.resolvable(self.feed, entry), True)
        resolver.resolve(self.feed, entry)
        self.assertEqual(entry['url'], 'http://www.nyaatorrents.org/?page=download&tid=12345')


class TestDisableBuiltins(FlexGetTestCase):

    """
        Quick hack, test disable functionality by checking if seen filtering (builtin) is working
    """
        
    def setUp(self):
        self.config = 'test/disable_builtins.yml'
        FlexGetTestCase.setUp(self)

    def testDisableBuiltins(self):
        self.execute_feed('test')
        if not (self.feed.find_entry(title='dupe1') and self.feed.find_entry(title='dupe2')):
            self.fail('disable_builtins is not working?')
        
        
class TestManager(FlexGetTestCase):

    def setUp(self):
        # just load with some conf
        self.config = 'test/regexp.yml'
        FlexGetTestCase.setUp(self)
        
    def testFailed(self):
        pass
        """
        e = Entry()
        e['title'] = 'test'
        e['url'] = 'http://localhost/mock'
        self.manager.add_failed(e)
        assert len(self.manager.shelve_session['failed']) == 1, 'failed to add'
        e = Entry()
        e['title'] = 'test 2'
        e['url'] = 'http://localhost/mock'
        self.manager.add_failed(e)
        assert len(self.manager.shelve_session['failed']) == 2, 'failed to add again'
        self.manager.add_failed(e)
        assert len(self.manager.shelve_session['failed']) == 2, 'failed to filter already added'
        """
        
    def testBsImport(self):
        import BeautifulSoup
        if BeautifulSoup.__version__ != '3.0.7a':
            self.fail('BeautifulSoup version wrong')


class TestInputHtml(FlexGetTestCase):
        
    def setUp(self):
        self.config = 'test/html.yml'
        FlexGetTestCase.setUp(self)
        
    def testParsing(self):
        self.execute_feed('test')
        if not self.feed.entries:
            self.fail('did not produce entries')


class TestFilterSeen(FlexGetTestCase):
        
    def setUp(self):
        self.config = 'test/seen.yml'
        FlexGetTestCase.setUp(self)
        
    def testSeen(self):
        self.execute_feed('test')
        if not self.feed.find_entry(title='Seen title 1'):
            self.fail('Test entry missing')
        # run again, should filter
        self.feed.execute()
        if self.feed.find_entry(title='Seen title 1'):
            self.fail('Seen test entry remains')
            
        # execute another feed
        
        self.execute_feed('test2')
        # should not contain since fields seen in previous feed
        if self.feed.find_entry(title='Seen title 1'):
            self.fail('Seen test entry 1 remains in second feed')
        if self.feed.find_entry(title='Seen title 2'):
            self.fail('Seen test entry 2 remains in second feed')
        # new item in feed should exists
        if not self.feed.find_entry(title='Seen title 3'):
            self.fail('Unseen test entry 3 not in second feed')
            
        # test that we don't filter reject on non-string fields (ie, seen same imdb_score)

        self.execute_feed('test_number')
        if not self.feed.find_entry(title='New title 1') or not self.feed.find_entry(title='New title 2'):
            self.fail('Item should not have been rejected because of number field')
            

class TestFilterSeenMovies(FlexGetTestCase):

    def setUp(self):
        self.config = 'test/seen_movies.yml'
        FlexGetTestCase.setUp(self)
            
    def testSeenMovies(self):
        self.execute_feed('test')
        if not self.feed.find_entry(title='Seen movie title 1'):
            self.fail('Test movie entry 1 is missing')
        # should be rejected, duplicate imdb url
        if self.feed.find_entry(title='Seen movie title 2'):
            self.fail('Test movie entry 2 should be rejected')
        # execute again
        self.feed.execute()
        if self.feed.find_entry(title='Seen movie title 1'):
            self.fail('Test movie entry 1 should be rejected in second execution')
        if self.feed.find_entry(title='Seen movie title 2'):
            self.fail('Test movie entry 2 should be rejected in second execution')

        # execute another feed
        
        self.execute_feed('test2')

        # should not contain since fields seen in previous feed
        if self.feed.find_entry(title='Seen movie title 3'):
            self.fail('seen movie 3 exists')
        if self.feed.find_entry(title='Seen movie title 4'):
            self.fail('seen movie 4 exists')
        if not self.feed.find_entry(title='Seen movie title 5'):
            self.fail('unseen movie 5 exists')
    
    def testSeenMoviesStrict(self):
        self.execute_feed('strict')
        if self.feed.find_entry(title='Seen movie title 8'):
            self.fail('strict should not have passed movie 8')

class TestDownload(FlexGetTestCase):

    def setUp(self):
        self.config = 'test/download.yml'
        FlexGetTestCase.setUp(self)

    def testDownload(self):
        self.testfile = os.path.expanduser('~/flexget_test_data')
        if os.path.exists(self.testfile):
            os.remove(self.testfile)
        # executes feed and downloads the file
        self.execute_feed('test')
        if not os.path.exists(self.testfile):
            self.fail('download file does not exists')
        else:
            os.remove(self.testfile)    

class TestInputRSS(FlexGetTestCase):

    def setUp(self):
        self.config = 'test/rss.yml'
        FlexGetTestCase.setUp(self)

    def testInputRSS(self):
        self.execute_feed('test')
        
        # normal entry
        if not self.feed.find_entry(title='Normal', url='http://localhost/normal', \
                                    description='Description, normal'):
            self.fail('RSS entry missing: normal')
        
        # multiple enclosures
        if not self.feed.find_entry(title='Multiple enclosures', url='http://localhost/enclosure1', \
                                    filename='enclosure1', description='Description, multiple'):
            self.fail('RSS entry missing: enclosure1')
        if not self.feed.find_entry(title='Multiple enclosures', url='http://localhost/enclosure2', \
                                    filename='enclosure2', description='Description, multiple'):
            self.fail('RSS entry missing: enclosure2')
        if not self.feed.find_entry(title='Multiple enclosures', url='http://localhost/enclosure3', \
                                    filename='enclosure3', description='Description, multiple'):
            self.fail('RSS entry missing: enclosure3')
        
        # zero sized enclosure should not pick up filename (some idiotic sites)
        e = self.feed.find_entry(title='Zero sized enclosure')
        if not e:
            self.fail('RSS entry missing: zero sized')
        if e.has_key('filename'):
            self.fail('RSS entry with 0-sized enclosure should not have explicit filename')
        
        # messy enclosure
        e = self.feed.find_entry(title='Messy enclosure')
        if not e:
            self.fail('RSS entry missing: messy')
        if not e.has_key('filename'):
            self.fail('Messy RSS enclosure: missing filename')
        if e['filename'] != 'enclosure.mp3':
            self.fail('Messy RSS enclosure: wrong filename')
        
        # pick link from guid
        if not self.feed.find_entry(title='Guid link', url='http://localhost/guid', \
                                    description='Description, guid'):
            self.fail('RSS entry missing: guid')
            
        # empty title, should be skipped
        if self.feed.find_entry(description='Description, empty title'):
            self.fail('RSS entry without title should be skipped')


class TestImdbOnline(FlexGetTestCase):

    def setUp(self):
        self.config = 'test/imdb.yml'
        FlexGetTestCase.setUp(self)
        
    def testMovies(self):
        self.execute_feed('test')
        if not self.feed.find_entry(imdb_name='Sen to Chihiro no kamikakushi'):
            self.fail('Failed imdb lookup (search)')
        if not self.feed.find_entry(imdb_name='Mononoke-hime'):
            self.fail('Failed imdb lookup (direct)')
        if not self.feed.find_entry(imdb_name='Taken', imdb_url='http://www.imdb.com/title/tt0936501/'):
            self.fail('Failed to pick correct Taken from search results')

    def testYear(self):
        self.execute_feed('year')
        if not self.feed.find_entry('accepted', imdb_name='Taken'):
            self.fail('Taken should\'ve been accepted')
        if not self.feed.find_entry('rejected', imdb_name='Mononoke-hime'):
            self.fail('Mononoke-hime should\'ve been rejected')

class TestRssOnline(FlexGetTestCase):

    def setUp(self):
        self.config = 'test/rss_online.yml'
        FlexGetTestCase.setUp(self)
        
    def testFeeds(self):
        # TODO:
        pass

class TestScanImdb(FlexGetTestCase):
    
    def setUp(self):
        self.config = 'test/scan_imdb.yml'
        FlexGetTestCase.setUp(self)

    def testScanImdb(self):
        self.execute_feed('test')
        if not self.feed.find_entry(imdb_url='http://www.imdb.com/title/tt0330793'):
            self.fail('Failed pick url from test 1')
        if not self.feed.find_entry(imdb_url='http://imdb.com/title/tt0472198'):
            self.fail('Failed pick url from test 2')

class TestValidator(unittest.TestCase):

    def testDefault(self):
        root = validator.factory()
        assert root.name=='root', 'expected root'
        dv = root.accept('dict')
        assert dv.name=='dict', 'expected dict'
        dv.accept('text', key='text')
        
    def testDict(self):
        dv = validator.factory('dict')
        dv.accept('dict', key='foo')
        result = dv.validate( {'foo': {}} )
        if dv.errors.messages:
            self.fail('should have passed foo')
        if not result:
            self.fail('invalid result for foo')
        result = dv.validate( {'bar': {}} )
        if not dv.errors.messages:
            self.fail('should not have passed bar')                    
        if result:
            self.fail('invalid result for bar')

def test_all():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestRegexp))
    suite.addTest(unittest.makeSuite(TestResolvers))
    suite.addTest(unittest.makeSuite(TestFilterSeries))
    suite.addTest(unittest.makeSuite(TestFilterSeen))
    suite.addTest(unittest.makeSuite(TestFilterSeenMovies))
    suite.addTest(unittest.makeSuite(TestManager))
    suite.addTest(unittest.makeSuite(TestInputRSS))
    suite.addTest(unittest.makeSuite(TestDisableBuiltins))
    suite.addTest(unittest.makeSuite(TestValidator))
    suite.addTest(unittest.makeSuite(TestScanImdb))
    
    if '--online' in sys.argv:
        print 'NOTE: Online tests are enabled. Some of these may fail since they depend on 3rd party services.'
        suite.addTest(unittest.makeSuite(TestImdbOnline))
        suite.addTest(unittest.makeSuite(TestDownload))
        suite.addTest(unittest.makeSuite(TestInputHtml))
        suite.addTest(unittest.makeSuite(TestRssOnline))
    else:
        print 'NOTE: Use --online argument to enable online tests.'
    
    # run suite
    unittest.TextTestRunner(verbosity=2).run(suite)

if __name__ == '__main__':
    test_all()
