from tests import FlexGetBase

class TestFilterSeries(FlexGetBase):
    
    __yaml__ = """
        feeds:
          test:
            input_mock:
              - {title: 'Some.Series.S01E20.720p.XViD-FlexGet'}
              - {title: 'Another.Series.S01E20.720p.XViD-FlexGet'}
              - {title: 'Another.Series.S01E10.720p.XViD-FlexGet'}
              - {title: 'Another.Series.S01E16.720p.XViD-FlexGet'}
              - {title: 'Another.Series.S01E21.1080p.H264-FlexGet'}
              - {title: 'Date.Series.10-11-2008.XViD'}
              - {title: 'Date.Series.10.12.2008.XViD'}
              - {title: 'Date.Series.2008-10-13.XViD'}
              - {title: 'Date.Series.2008x10.14.XViD'}
              - {title: 'Useless title', filename: 'Filename.Series.S01E26.XViD'}
              - {title: 'Empty.Description.S01E22.XViD', description: ''}
              
            regexp:
              reject:
                - 1080p
            series:
              - some series:
                  quality: 1080p
                  timeframe: 4 hours
              - another series
              - date series
              - filename series
              - empty description
              
          test_propers_1:
            input_mock:
              - {title: 'Test.S01E01.720p-FlexGet'}
            series:
              - test
            # prevents seen from rejecting on second execution, 
            # we want to see that series is able to reject
            disable_builtins: yes
    
          test_propers_2:
            input_mock:
              - {title: 'Test.S01E01.720p.Proper-FlexGet'}
            series:
              - test
            # prevents seen from rejecting on second execution, 
            # we want to see that series is able to reject
            disable_builtins: yes
            
          test_quality:
            input_mock:
              - {title: 'QTest.S01E01.HDTV.XViD-FlexGet'}
              - {title: 'QTest.S01E01.PDTV.XViD-FlexGet'}
              - {title: 'QTest.S01E01.DSR.XViD-FlexGet'}
              - {title: 'QTest.S01E01.1080p.XViD-FlexGet'}
              - {title: 'QTest.S01E01.720p.XViD-FlexGet'}
            series:
              - QTest:
                  quality: 720p
    """
    
    def setup(self):
        FlexGetBase.setUp(self)

    def test_quality(self):
        self.execute_feed('test_quality')
        assert self.feed.find_entry('accepted', title='QTest.S01E01.720p.XViD-FlexGet'), '720p should have been accepted'
        assert not self.feed.find_entry('accepted', title='QTest.S01E01.HDTV.XViD-FlexGet'), 'hdtv shouldn\'t have been accepted'
        assert not self.feed.find_entry('accepted', title='QTest.S01E01.PDTV.XViD-FlexGet'), 'pdtv shouldn\'t have been accepted'
        assert not self.feed.find_entry('accepted', title='QTest.S01E01.1080p.XViD-FlexGet'), '1080p shouldn\'t have been accepted'
        assert not self.feed.find_entry('accepted', title='QTest.S01E01.DSR.XViD-FlexGet'), 'DSR shouldn\'t have been accepted'

    def test_smoke(self):
        self.execute_feed('test')
        # TODO: needs to be fixed after series is converted into SQLAlchemy
        # 'some series' should be in timeframe-queue
        #self.feed.shared_cache.set_namespace('series')
        #s = self.feed.shared_cache.get('some series')
        #assert isinstance(s, dict)
        #assert not s.get('S1E20', {}).get('info').get('downloaded')
        
        # normal passing
        assert self.feed.find_entry(title='Another.Series.S01E20.720p.XViD-FlexGet'), 'Another.Series.S01E20.720p.XViD-FlexGet should have passed'

        # date formats
        df = ['Date.Series.10-11-2008.XViD','Date.Series.10.12.2008.XViD', 'Date.Series.2008-10-13.XViD', 'Date.Series.2008x10.14.XViD']
        for d in df:
            assert self.feed.find_entry(title=d), 'Date format did not match %s' % d
        
        # parse from filename
        assert self.feed.find_entry(filename='Filename.Series.S01E26.XViD'), 'Filename parsing failed'
        
        # empty description
        assert self.feed.find_entry(title='Empty.Description.S01E22.XViD'), 'Empty Description failed'
        
        # chaining with regexp plugin
        assert self.feed.find_entry('rejected', title='Another.Series.S01E21.1080p.H264-FlexGet'), 'regexp rejection'
        
        # episode advancement (tracking)
        assert self.feed.find_entry('rejected', title='Another.Series.S01E10.720p.XViD-FlexGet'), 'Another.Series.S01E10.720p.XViD-FlexGet should be rejected due advancement'
        assert self.feed.find_entry('accepted', title='Another.Series.S01E16.720p.XViD-FlexGet'), 'Another.Series.S01E16.720p.XViD-FlexGet should have passed because of episode advancement grace magin'
        
    def test_propers(self):
        self.execute_feed('test_propers_1')
        assert self.feed.find_entry('accepted', title='Test.S01E01.720p-FlexGet'), 'Test.S01E01-FlexGet should have been accepted'
        # rejects downloaded
        self.execute_feed('test_propers_1')
        assert self.feed.find_entry('rejected', title='Test.S01E01.720p-FlexGet'), 'Test.S01E01-FlexGet should have been rejected'
        # accepts proper
        self.execute_feed('test_propers_2')
        assert self.feed.find_entry('accepted', title='Test.S01E01.720p.Proper-FlexGet'), 'Test.S01E01.Proper-FlexGet should have been accepted'
        # reject downloaded proper
        self.execute_feed('test_propers_2')
        assert self.feed.find_entry('rejected', title='Test.S01E01.720p.Proper-FlexGet'), 'Test.S01E01.Proper-FlexGet should have been rejected'

        
class TestFilterSeriesPriority(FlexGetBase):
    __yaml__ = """
        feeds:
          test:
            input_mock:
              - {title: 'foobar 720p s01e01', url: 'http://localhost/1' }
              - {title: 'foobar hdtv s01e01', url: 'http://localhost/2' }
            regexp:
              reject:
                - 720p
            series:
              - foobar
    """    

    def setup(self):
        FlexGetBase.setUp(self)
        self.execute_feed('test')

    def test_priorities(self):
        assert self.feed.find_entry('rejected', title='foobar 720p s01e01'), 'foobar 720p s01e01 should have been rejected'
        assert self.feed.find_entry('accepted', title='foobar hdtv s01e01'), 'foobar hdtv s01e01 is not accepted'
class TestSimilarNames(FlexGetBase):

    # hmm, not very good way to test this .. seriesparser should be tested alone?

    __yaml__ = """
        feeds:
          test:
            input_mock:
              - {title: 'FooBar.S03E01.DSR-FlexGet'}
              - {title: 'FooBar: FirstAlt.S02E01.DSR-FlexGet'}
              - {title: 'FooBar: SecondAlt.S01E01.DSR-FlexGet'}
            series:
              - FooBar
              - "FooBar: FirstAlt"
              - "FooBar: SecondAlt"
    """    

    def setUp(self):
        FlexGetBase.setUp(self)
        self.execute_feed('test')

    def testNames(self):
        assert self.feed.find_entry('accepted', title='FooBar.S03E01.DSR-FlexGet'), 'Standard failed?'
        assert self.feed.find_entry('accepted', title='FooBar: FirstAlt.S02E01.DSR-FlexGet'), 'FirstAlt failed'
        assert self.feed.find_entry('accepted', title='FooBar: SecondAlt.S01E01.DSR-FlexGet'), 'SecondAlt failed'

class TestRemembering(FlexGetBase):

    # Added to test one possible bug report, no bug found (useless test?)

    __yaml__ = """
        feeds:
          test_1:
            input_mock:
              - {title: 'Foo.2009.S02E04.HDTV.XviD-2HD[FlexGet]'}
            series:
              - Foo 2009
          test_2:
            input_mock:
              - {title: 'Foo.2009.S02E04.HDTV.XviD-2HD[ASDF]'}
            series:
              - Foo 2009
    """

    def test_foo(self):
        self.execute_feed('test_1')
        assert self.feed.find_entry('accepted', title='Foo.2009.S02E04.HDTV.XviD-2HD[FlexGet]'), 'Did not accept Foo.2009.S02E04.HDTV.XviD-FlexGet'
        self.execute_feed('test_2')
        assert self.feed.find_entry('rejected', title='Foo.2009.S02E04.HDTV.XviD-2HD[ASDF]'), 'Did not reject Foo.2009.S02E04.HDTV.XviD-ASDF'


class TestDuplicates(FlexGetBase):

    __yaml__ = """
        feeds:
          test:
            input_mock:
              - {title: 'Foo.2009.S02E04.HDTV.XviD-2HD[FlexGet]'}
              - {title: 'Foo.2009.S02E04.HDTV.XviD-2HD[ASDF]'}
            series:
              - Foo 2009
    """

    def test_dupes(self):
        self.execute_feed('test')
        self.dump()
        assert not (self.feed.find_entry('accepted', title='Foo.2009.S02E04.HDTV.XviD-2HD[FlexGet]') and \
                    self.feed.find_entry('accepted', title='Foo.2009.S02E04.HDTV.XviD-2HD[ASDF]')), 'accepted both'

