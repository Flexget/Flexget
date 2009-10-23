from tests import FlexGetBase

class TestQuality(FlexGetBase):

    __yaml__ = """
        feeds:
          best_quality:
            input_mock:
              - {title: 'QTest.S01E01.HDTV.XViD-FlexGet'}
              - {title: 'QTest.S01E01.PDTV.XViD-FlexGet'}
              - {title: 'QTest.S01E01.DSR.XViD-FlexGet'}
              - {title: 'QTest.S01E01.1080p.XViD-FlexGet'}
              - {title: 'QTest.S01E01.720p.XViD-FlexGet'}
            series:
              - QTest:
                  quality: 720p

          min_quality:
            input_mock:
              - {title: 'MinQTest.S01E01.HDTV.XViD-FlexGet'}
              - {title: 'MinQTest.S01E01.PDTV.XViD-FlexGet'}
              - {title: 'MinQTest.S01E01.DSR.XViD-FlexGet'}
              - {title: 'MinQTest.S01E01.1080p.XViD-FlexGet'}
              - {title: 'MinQTest.S01E01.720p.XViD-FlexGet'}
            series:
              - MinQTest:
                  min_quality: hdtv

          max_quality:
            input_mock:
              - {title: 'MaxQTest.S01E01.HDTV.XViD-FlexGet'}
              - {title: 'MaxQTest.S01E01.PDTV.XViD-FlexGet'}
              - {title: 'MaxQTest.S01E01.DSR.XViD-FlexGet'}
              - {title: 'MaxQTest.S01E01.1080p.XViD-FlexGet'}
              - {title: 'MaxQTest.S01E01.720p.XViD-FlexGet'}
            series:
              - MaxQTest:
                  max_quality: hdtv

          min_max_quality:
            input_mock:
              - {title: 'MinMaxQTest.S01E01.HDTV.XViD-FlexGet'}
              - {title: 'MinMaxQTest.S01E01.PDTV.XViD-FlexGet'}
              - {title: 'MinMaxQTest.S01E01.DSR.XViD-FlexGet'}
              - {title: 'MinMaxQTest.S01E01.720p.XViD-FlexGet'}
              - {title: 'MinMaxQTest.S01E01.HR.XViD-FlexGet'}
              - {title: 'MinMaxQTest.S01E01.1080p.XViD-FlexGet'}
            series:
              - MinMaxQTest:
                  min_quality: pdtv
                  max_quality: hr
    """

    def test_best_quality(self):
        """Series plugin: choose by quality"""
        self.execute_feed('best_quality')
        assert self.feed.find_entry('accepted', title='QTest.S01E01.720p.XViD-FlexGet'), \
            '720p should have been accepted'
        assert len(self.feed.accepted) == 1, 'should have accepted only one'
            
    def test_min_quality(self):
        """Series plugin: min_quality"""
        self.execute_feed('min_quality')
        assert self.feed.find_entry('accepted', title='MinQTest.S01E01.1080p.XViD-FlexGet'), \
            'MinQTest.S01E01.1080p.XViD-FlexGet should have been accepted'
        assert len(self.feed.accepted) == 1, 'should have accepted only one'
            
    def test_max_quality(self):
        """Series plugin: max_quality"""
        self.execute_feed('max_quality')
        assert self.feed.find_entry('accepted', title='MaxQTest.S01E01.HDTV.XViD-FlexGet'), \
            'MaxQTest.S01E01.HDTV.XViD-FlexGet should have been accepted'
        assert len(self.feed.accepted) == 1, 'should have accepted only one'
    
    def test_min_max_quality(self):
        """Series plugin: min_quality with max_quality"""
        self.execute_feed('min_max_quality')
        assert self.feed.find_entry('accepted', title='MinMaxQTest.S01E01.HR.XViD-FlexGet'), \
            'MinMaxQTest.S01E01.HR.XViD-FlexGet should have been accepted'
        assert len(self.feed.accepted) == 1, 'should have accepted only one'


class TestTracking(FlexGetBase):
    __yaml__ = """
        global:
          series:
            - some series

        feeds:
          test_1:
            input_mock:
              - {title: 'Some.Series.S01E20.720p.XViD-FlexGet'}
          test_2:
            input_mock:
              - {title: 'Some.Series.S01E20.720p.XViD-DoppelGanger'}
    """

    def test_tracking(self):
        self.execute_feed('test_1')
        self.execute_feed('test_2')
        assert self.feed.find_entry('rejected', title='Some.Series.S01E20.720p.XViD-DoppelGanger'), \
            'failed basic download tracking'

class TestFilterSeries(FlexGetBase):

    # TODO: TOO LARGE
    
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
            
    """
    

    def test_smoke(self):
        """Series plugin: test several standard features"""
        self.execute_feed('test')
        # TODO: needs to be fixed after series is converted into SQLAlchemy
        # 'some series' should be in timeframe-queue
        #self.feed.shared_cache.set_namespace('series')
        #s = self.feed.shared_cache.get('some series')
        #assert isinstance(s, dict)
        #assert not s.get('S1E20', {}).get('info').get('downloaded')
        
        # normal passing
        assert self.feed.find_entry(title='Another.Series.S01E20.720p.XViD-FlexGet'), \
            'Another.Series.S01E20.720p.XViD-FlexGet should have passed'

        # date formats
        df = ['Date.Series.10-11-2008.XViD','Date.Series.10.12.2008.XViD', \
              'Date.Series.2008-10-13.XViD', 'Date.Series.2008x10.14.XViD']
        for d in df:
            assert self.feed.find_entry(title=d), 'Date format did not match %s' % d
        
        # parse from filename
        assert self.feed.find_entry(filename='Filename.Series.S01E26.XViD'), 'Filename parsing failed'
        
        # empty description
        assert self.feed.find_entry(title='Empty.Description.S01E22.XViD'), 'Empty Description failed'
        
        # chaining with regexp plugin
        assert self.feed.find_entry('rejected', title='Another.Series.S01E21.1080p.H264-FlexGet'), \
            'regexp rejection'
        
        # episode advancement (tracking)
        assert self.feed.find_entry('rejected', title='Another.Series.S01E10.720p.XViD-FlexGet'), \
            'Another.Series.S01E10.720p.XViD-FlexGet should be rejected due advancement'
        assert self.feed.find_entry('accepted', title='Another.Series.S01E16.720p.XViD-FlexGet'), \
            'Another.Series.S01E16.720p.XViD-FlexGet should have passed because of episode advancement grace magin'

        
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

    def test_priorities(self):
        self.execute_feed('test')
        """Series plugin: regexp plugin is able to reject before series plugin"""
        assert self.feed.find_entry('rejected', title='foobar 720p s01e01'), \
            'foobar 720p s01e01 should have been rejected'
        assert self.feed.find_entry('accepted', title='foobar hdtv s01e01'), \
            'foobar hdtv s01e01 is not accepted'


class TestPropers(FlexGetBase):

    __yaml__ = """
        global:
          # prevents seen from rejecting on second execution,
          # we want to see that series is able to reject
          disable_builtins: yes
          series:
            - test
            - foobar

        feeds:
          test_propers_1:
            input_mock:
              - {title: 'Test.S01E01.720p-FlexGet'}

          # introduce proper, should be accepted
          test_propers_2:
            input_mock:
              - {title: 'Test.S01E01.720p.Proper-FlexGet'}

          # introduce non-proper, should not be downloaded
          test_propers_3:
            input_mock:
              - {title: 'Test.S01E01.FlexGet'}

          # introduce proper at the same time, should nuke non-proper and get proper
          test_propers_4:
            input_mock:
              - {title: 'Foobar.S01E01.720p.FlexGet'}
              - {title: 'Foobar.S01E01.720p.proper.FlexGet'}
    """

    def test_propers(self):
        """Series plugin: propers are accepted after episode is downloaded"""
        self.execute_feed('test_propers_1')
        assert self.feed.find_entry('accepted', title='Test.S01E01.720p-FlexGet'), \
            'Test.S01E01-FlexGet should have been accepted'
        # rejects downloaded
        self.execute_feed('test_propers_1')
        assert self.feed.find_entry('rejected', title='Test.S01E01.720p-FlexGet'), \
            'Test.S01E01-FlexGet should have been rejected'
        # accepts proper
        self.execute_feed('test_propers_2')
        assert self.feed.find_entry('accepted', title='Test.S01E01.720p.Proper-FlexGet'), \
            'Test.S01E01.Proper-FlexGet should have been accepted'
        # reject downloaded proper
        self.execute_feed('test_propers_2')
        assert self.feed.find_entry('rejected', title='Test.S01E01.720p.Proper-FlexGet'), \
            'Test.S01E01.Proper-FlexGet should have been rejected'
        # reject episode that has been downloaded normally and with proper
        self.execute_feed('test_propers_3')
        assert self.feed.find_entry('rejected', title='Test.S01E01.FlexGet'), \
            'Test.S01E01.FlexGet should have been rejected'

    def test_proper_available(self):
        """Series plugin: proper available immediately"""
        self.execute_feed('test_propers_4')
        self.dump()
        assert self.feed.find_entry('accepted', title='Foobar.S01E01.720p.proper.FlexGet'), \
            'Foobar.S01E01.720p.proper.FlexGet should have been accepted'


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

    def setup(self):
        FlexGetBase.setUp(self)
        self.execute_feed('test')

    def test_names(self):
        assert self.feed.find_entry('accepted', title='FooBar.S03E01.DSR-FlexGet'), 'Standard failed?'
        assert self.feed.find_entry('accepted', title='FooBar: FirstAlt.S02E01.DSR-FlexGet'), 'FirstAlt failed'
        assert self.feed.find_entry('accepted', title='FooBar: SecondAlt.S01E01.DSR-FlexGet'), 'SecondAlt failed'

class TestDuplicates(FlexGetBase):

    __yaml__ = """
        
        global: # just cleans log a bit ..
          disable_builtins:
            - seen
            
        feeds:
          test_dupes:
            input_mock:
              - {title: 'Foo.2009.S02E04.HDTV.XviD-2HD[FlexGet]'}
              - {title: 'Foo.2009.S02E04.HDTV.XviD-2HD[ASDF]'}
            series:
              - Foo 2009

          test_1:
            input_mock:
              - {title: 'Foo.Bar.S02E04.HDTV.XviD-2HD[FlexGet]'}
              - {title: 'Foo.Bar.S02E04.HDTV.XviD-2HD[ASDF]'}
            series:
              - foo bar

          test_2:
            input_mock:
              - {title: 'Foo.Bar.S02E04.XviD-2HD[ASDF]'}
              - {title: 'Foo.Bar.S02E04.HDTV.720p.XviD-2HD[FlexGet]'}
              - {title: 'Foo.Bar.S02E04.DSRIP.XviD-2HD[ASDF]'}
              - {title: 'Foo.Bar.S02E04.HDTV.1080p.XviD-2HD[ASDF]'}
              - {title: 'Foo.Bar.S02E03.HDTV.XviD-FlexGet'}
              - {title: 'Foo.Bar.S02E05.HDTV.XviD-ZZZ'}
              - {title: 'Foo.Bar.S02E05.720p.HDTV.XviD-YYY'}
            series:
              - foo bar

          test_true_dupes:
            input_mock:
              - {title: 'Dupe.S02E04.HDTV.XviD-FlexGet'}
              - {title: 'Dupe.S02E04.HDTV.XviD-FlexGet'}
              - {title: 'Dupe.S02E04.HDTV.XviD-FlexGet'}
            series:
              - dupe
    """

    def test_dupes(self):
        """Series plugin: dupes with same quality"""
        self.execute_feed('test_dupes')
        assert len(self.feed.accepted) == 1, 'accepted both'


    def test_true_dupes(self):
        """Series plugin: true duplicate items"""
        self.execute_feed('test_true_dupes')
        self.dump()
        assert len(self.feed.accepted) == 1, 'should have accepted (only) one'

    def test_downloaded(self):
        """Series plugin: multiple downloaded and new episodes are handled correctly"""

        self.execute_feed('test_1')
        self.execute_feed('test_2')

        # these should be accepted
        accepted = ['Foo.Bar.S02E03.HDTV.XviD-FlexGet', 'Foo.Bar.S02E05.720p.HDTV.XviD-YYY']
        for item in accepted:
            assert self.feed.find_entry('accepted', title=item), \
                '%s should have been accepted' % item

        # these should be rejected
        rejected = ['Foo.Bar.S02E04.XviD-2HD[ASDF]', 'Foo.Bar.S02E04.HDTV.720p.XviD-2HD[FlexGet]', \
                    'Foo.Bar.S02E04.DSRIP.XviD-2HD[ASDF]', 'Foo.Bar.S02E04.HDTV.1080p.XviD-2HD[ASDF]']
        for item in rejected:
            assert self.feed.find_entry('rejected', title=item), \
                '%s should have been rejected' % item

class TestQualities(FlexGetBase):

    __yaml__ = """
        feeds:
          test:
            input_mock:
              - {title: 'FooBar.S01E01.PDTV-FlexGet'}
              - {title: 'FooBar.S01E01.720p-FlexGet'}
              - {title: 'FooBar.S01E01.1080p-FlexGet'}
              - {title: 'FooBar.S01E01.HR-FlexGet'}
            series:
              - FooBar:
                  qualities:
                    - PDTV
                    - 720p
                    - 1080p
    """

    def test_qualities(self):
        self.execute_feed('test')

        assert self.feed.find_entry('accepted', title='FooBar.S01E01.PDTV-FlexGet'), \
            'Didn''t accept FooBar.S01E01.PDTV-FlexGet'
        assert self.feed.find_entry('accepted', title='FooBar.S01E01.720p-FlexGet'), \
            'Didn''t accept FooBar.S01E01.720p-FlexGet'
        assert self.feed.find_entry('accepted', title='FooBar.S01E01.1080p-FlexGet'), \
            'Didn''t accept FooBar.S01E01.1080p-FlexGet'

        assert not self.feed.find_entry('accepted', title='FooBar.S01E01.HR-FlexGet'), \
            'Accepted FooBar.S01E01.HR-FlexGet'

        # test that it rejects them after

        self.execute_feed('test')

        assert self.feed.find_entry('rejected', title='FooBar.S01E01.PDTV-FlexGet'), \
            'Didn''t rehect FooBar.S01E01.PDTV-FlexGet'
        assert self.feed.find_entry('rejected', title='FooBar.S01E01.720p-FlexGet'), \
            'Didn''t reject FooBar.S01E01.720p-FlexGet'
        assert self.feed.find_entry('rejected', title='FooBar.S01E01.1080p-FlexGet'), \
            'Didn''t reject FooBar.S01E01.1080p-FlexGet'

        assert not self.feed.find_entry('accepted', title='FooBar.S01E01.HR-FlexGet'), \
            'Accepted FooBar.S01E01.HR-FlexGet'
