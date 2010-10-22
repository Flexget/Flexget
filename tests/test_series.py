from tests import FlexGetBase


def age_series(**kwargs):
    from flexget.plugins.filter_series import Series
    from flexget.manager import Session
    import datetime
    session = Session()
    for series in session.query(Series).all():
        for episode in series.episodes:
            episode.first_seen = datetime.datetime.now() - datetime.timedelta(**kwargs)
    session.commit()


class TestQuality(FlexGetBase):

    __yaml__ = """
        feeds:
          best_quality:
            mock:
              - {title: 'QTest.S01E01.HDTV.XViD-FlexGet'}
              - {title: 'QTest.S01E01.PDTV.XViD-FlexGet'}
              - {title: 'QTest.S01E01.DSR.XViD-FlexGet'}
              - {title: 'QTest.S01E01.1080p.XViD-FlexGet'}
              - {title: 'QTest.S01E01.720p.XViD-FlexGet'}
            series:
              - QTest:
                  quality: 720p

          min_quality:
            mock:
              - {title: 'MinQTest.S01E01.HDTV.XViD-FlexGet'}
              - {title: 'MinQTest.S01E01.PDTV.XViD-FlexGet'}
              - {title: 'MinQTest.S01E01.DSR.XViD-FlexGet'}
              - {title: 'MinQTest.S01E01.1080p.XViD-FlexGet'}
              - {title: 'MinQTest.S01E01.720p.XViD-FlexGet'}
            series:
              - MinQTest:
                  min_quality: hdtv

          max_quality:
            mock:
              - {title: 'MaxQTest.S01E01.HDTV.XViD-FlexGet'}
              - {title: 'MaxQTest.S01E01.PDTV.XViD-FlexGet'}
              - {title: 'MaxQTest.S01E01.DSR.XViD-FlexGet'}
              - {title: 'MaxQTest.S01E01.1080p.XViD-FlexGet'}
              - {title: 'MaxQTest.S01E01.720p.XViD-FlexGet'}
            series:
              - MaxQTest:
                  max_quality: HDTV

          min_max_quality:
            mock:
              - {title: 'MinMaxQTest.S01E01.HDTV.XViD-FlexGet'}
              - {title: 'MinMaxQTest.S01E01.PDTV.XViD-FlexGet'}
              - {title: 'MinMaxQTest.S01E01.DSR.XViD-FlexGet'}
              - {title: 'MinMaxQTest.S01E01.720p.XViD-FlexGet'}
              - {title: 'MinMaxQTest.S01E01.HR.XViD-FlexGet'}
              - {title: 'MinMaxQTest.S01E01.1080p.XViD-FlexGet'}
            series:
              - MinMaxQTest:
                  min_quality: sdtv
                  max_quality: hr
                  
          max_unknown_quality:
            mock:
              - {title: 'MaxUnknownQTest.S01E01.XViD-FlexGet'}
            series:
              - MaxUnknownQTest:
                  max_quality: hdtv
                  
          description_quality:
            mock:
              - {'title': 'Description.S01E01', 'description': 'The quality should be 720p'}
            series:
              - description: {quality: 720p}

          quality_from_group:
            mock:
              - {title: 'GroupQual.S01E01.HDTV.XViD-FlexGet'}
              - {title: 'GroupQual.S01E01.PDTV.XViD-FlexGet'}
              - {title: 'GroupQual.S01E01.DSR.XViD-FlexGet'}
              - {title: 'GroupQual.S01E01.1080p.XViD-FlexGet'}
              - {title: 'GroupQual.S01E01.720p.XViD-FlexGet'}
            series:
              720P:
                - GroupQual
              # Test that an integer group name doesn't cause an exception.
              1080:
                - Test
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
        
    def test_max_unknown_quality(self):
        """Series plugin: max quality with unknown quality"""
        self.execute_feed('max_unknown_quality')
        assert len(self.feed.accepted) == 1, 'should have accepted'
        
    def test_quality_from_description(self):
        """Series plugin: quality from description"""
        self.execute_feed('description_quality')
        assert len(self.feed.accepted) == 1, 'should have accepted'

    def test_group_quality(self):
        """Series plugin: quality from group name"""
        self.execute_feed('quality_from_group')
        assert self.feed.find_entry('accepted', title='GroupQual.S01E01.720p.XViD-FlexGet'), \
            'GroupQual.S01E01.720p.XViD-FlexGet should have been accepted'
        assert len(self.feed.accepted) == 1, 'should have accepted only one'


class TestDatabase(FlexGetBase):

    __yaml__ = """
        presets:
          global:
            series:
              - some series
              - progress

        feeds:
          test_1:
            mock:
              - {title: 'Some.Series.S01E20.720p.XViD-FlexGet'}
          test_2:
            mock:
              - {title: 'Some.Series.S01E20.720p.XViD-DoppelGanger'}

          progress_1:
            mock:
              - {title: 'Progress.S01E20.720p-FlexGet'}
              - {title: 'Progress.S01E20.HDTV-FlexGet'}

          progress_2:
            mock:
              - {title: 'Progress.S01E20.720p.Another-FlexGet'}
              - {title: 'Progress.S01E20.HDTV-Another-FlexGet'}
    """

    def test_database(self):
        """Series plugin: simple database"""

        self.execute_feed('test_1')
        self.execute_feed('test_2')
        assert self.feed.find_entry('rejected', title='Some.Series.S01E20.720p.XViD-DoppelGanger'), \
            'failed basic download remembering'

    def test_doppelgangers(self):
        """Series plugin: doppelganger releases (dupes)"""

        self.execute_feed('progress_1')
        assert self.feed.find_entry('accepted', title='Progress.S01E20.720p-FlexGet'), \
            'best quality not accepted'
        # should not accept anything
        self.execute_feed('progress_1')
        assert not self.feed.accepted, 'repeated execution accepted'
        # introduce new doppelgangers
        self.execute_feed('progress_2')
        assert not self.feed.accepted, 'doppelgangers accepted'


class TestFilterSeries(FlexGetBase):

    __yaml__ = """
        feeds:
          test:
            mock:
              - {title: 'Another.Series.S01E20.720p.XViD-FlexGet'}
              - {title: 'Another.Series.S01E21.1080p.H264-FlexGet'}
              - {title: 'Date.Series.10-11-2008.XViD'}
              - {title: 'Date.Series.10.12.2008.XViD'}
              - {title: 'Date.Series.2008-10-13.XViD'}
              - {title: 'Date.Series.2008x10.14.XViD'}
              - {title: 'Useless title', filename: 'Filename.Series.S01E26.XViD'}
              - {title: 'Empty.Description.S01E22.XViD', description: ''}

            # test chaining
            regexp:
              reject:
                - 1080p

            series:
              - another series
              - date series
              - filename series
              - empty description

          metainfo_series_override:
            mock:
              - {title: 'Test.Series.with.extra.crap.S01E02.PDTV.XViD-FlexGet'}
              - {title: 'Other.Show.with.extra.crap.S02E01.PDTV.XViD-FlexGet'}
            series:
              - Test Series
    """

    def test_smoke(self):
        """Series plugin: test several standard features"""
        self.execute_feed('test')

        # normal passing
        assert self.feed.find_entry(title='Another.Series.S01E20.720p.XViD-FlexGet'), \
            'Another.Series.S01E20.720p.XViD-FlexGet should have passed'

        # date formats
        df = ['Date.Series.10-11-2008.XViD', 'Date.Series.10.12.2008.XViD', \
              'Date.Series.2008-10-13.XViD', 'Date.Series.2008x10.14.XViD']
        for d in df:
            assert self.feed.find_entry(title=d), 'Date format did not match %s' % d

        # parse from filename
        assert self.feed.find_entry(filename='Filename.Series.S01E26.XViD'), 'Filename parsing failed'

        # empty description
        assert self.feed.find_entry(title='Empty.Description.S01E22.XViD'), 'Empty Description failed'

        # chaining with regexp plugin
        assert self.feed.find_entry('rejected', title='Another.Series.S01E21.1080p.H264-FlexGet'), \
            'regexp chaining'

    def test_metainfo_series_override(self):
        """Series plugin: override metainfo_series"""
        self.execute_feed('metainfo_series_override')
        # Make sure the metainfo_series plugin is working first
        entry = self.feed.find_entry('entries', title='Other.Show.with.extra.crap.S02E01.PDTV.XViD-FlexGet')
        assert entry['series_guessed'], 'series should have been guessed'
        assert entry['series_name'] == entry['series_parser'].name == 'Other Show with extra crap', \
            'metainfo_series is not running'
        # Make sure the good series data overrode metainfo data for the listed series
        entry = self.feed.find_entry('accepted', title='Test.Series.with.extra.crap.S01E02.PDTV.XViD-FlexGet')
        assert not entry.get('series_guessed'), 'series plugin should override series_guessed'
        assert entry['series_name'] == entry['series_parser'].name == 'Test Series', \
            'Series name should be \'Test Series\', was: entry: %s, parser: %s' % (entry['series_name'], entry['series_parser'].name)


class TestEpisodeAdvancement(FlexGetBase):
    
    __yaml__ = """
        feeds:

          test_backwards_1:
            mock:
              - {title: 'backwards s01e12'}
              - {title: 'backwards s01e10'}
            series:
              - backwards

          test_backwards_2:
            mock:
              - {title: 'backwards s01e01'}
            series:
              - backwards

          test_forwards_1:
            mock:
              - {title: 'forwards s01e01'}
            series:
              - forwards

          test_forwards_2:
            mock:
              - {title: 'forwards s02e01'}
            series:
              - forwards
              
          test_forwards_3:
            mock:
              - {title: 'forwards s03e01'}
            series:
              - forwards
              
          test_forwards_4:
            mock:
              - {title: 'forwards s05e01'}
            series:
              - forwards

          test_unordered:
            mock:
              - {title: 'zzz s01e05'}
              - {title: 'zzz s01e06'}
              - {title: 'zzz s01e07'}
              - {title: 'zzz s01e08'}
              - {title: 'zzz s01e09'}
              - {title: 'zzz s01e10'}
              - {title: 'zzz s01e15'}
              - {title: 'zzz s01e14'}
              - {title: 'zzz s01e13'}
              - {title: 'zzz s01e12'}
              - {title: 'zzz s01e11'}
              - {title: 'zzz s01e01'}
            series:
              - zzz

    """

    def test_backwards(self):
        """Series plugin: episode advancement (backwards)"""
        self.execute_feed('test_backwards_1')
        assert self.feed.find_entry('accepted', title='backwards s01e12'), \
            'backwards s01e12 should have been accepted'
        assert self.feed.find_entry('accepted', title='backwards s01e10'), \
            'backwards s01e10 should have been accepted within grace margin'
        self.execute_feed('test_backwards_2')
        assert self.feed.find_entry('rejected', title='backwards s01e01'), \
            'backwards s01e01 should have been rejected, too old'
        
    def test_forwards(self):
        """Series plugin: episode advancement (future)"""
        self.execute_feed('test_forwards_1')
        assert self.feed.find_entry('accepted', title='forwards s01e01'), \
            'forwards s01e01 should have been accepted'
        self.execute_feed('test_forwards_2')
        assert self.feed.find_entry('accepted', title='forwards s02e01'), \
            'forwards s02e01 should have been accepted'
        self.execute_feed('test_forwards_3')
        assert self.feed.find_entry('accepted', title='forwards s03e01'), \
            'forwards s03e01 should have been accepted'
        self.execute_feed('test_forwards_4')
        assert self.feed.find_entry('rejected', title='forwards s05e01'), \
            'forwards s02e01 should have been rejected'

    def test_unordered(self):
        """Series plugin: unordered episode advancement"""
        self.execute_feed('test_unordered')
        assert len(self.feed.accepted) == 12, \
            'not everyone was accepted'


class TestFilterSeriesPriority(FlexGetBase):

    __yaml__ = """
        feeds:
          test:
            mock:
              - {title: 'foobar 720p s01e01'}
              - {title: 'foobar hdtv s01e01'}
            regexp:
              reject:
                - 720p
            series:
              - foobar
    """

    def test_priorities(self):
        """Series plugin: regexp plugin is able to reject before series plugin"""
        self.execute_feed('test')
        assert self.feed.find_entry('rejected', title='foobar 720p s01e01'), \
            'foobar 720p s01e01 should have been rejected'
        assert self.feed.find_entry('accepted', title='foobar hdtv s01e01'), \
            'foobar hdtv s01e01 is not accepted'


class TestPropers(FlexGetBase):

    __yaml__ = """
        presets:
          global:
            # prevents seen from rejecting on second execution,
            # we want to see that series is able to reject
            disable_builtins: yes
            series:
              - test
              - foobar
              - asfd:
                  min_quality: HR
                  max_quality: 1080p
              - V
              - tftest:
                  propers: 3 hours
              - notest:
                  propers: no

        feeds:
          propers_1:
            mock:
              - {title: 'Test.S01E01.720p-FlexGet'}

          # introduce proper, should be accepted
          propers_2:
            mock:
              - {title: 'Test.S01E01.720p.Proper-FlexGet'}

          # introduce non-proper, should not be downloaded
          propers_3:
            mock:
              - {title: 'Test.S01E01.FlexGet'}

          # introduce proper at the same time, should nuke non-proper and get proper
          proper_at_first:
            mock:
              - {title: 'Foobar.S01E01.720p.FlexGet'}
              - {title: 'Foobar.S01E01.720p.proper.FlexGet'}

          # test a lot of propers at once
          lot_propers:
            mock:
              - {title: 'V.2009.S01E01.PROPER.HDTV.A'}
              - {title: 'V.2009.S01E01.PROPER.HDTV.B'}
              - {title: 'V.2009.S01E01.PROPER.HDTV.C'}

          diff_quality_1:
            mock:
              - {title: 'Test.S01E02.720p-FlexGet'}

          # low quality proper, should not be accepted
          diff_quality_2:
            mock:
              - {title: 'Test.S01E02.HDTV.Proper-FlexGet'}

          # min + max quality with propers
          min_max_quality_1:
            mock:
              - {title: 'asfd.S01E01.720p-FlexGet'}
          min_max_quality_2:
            mock:
              - {title: 'asfd.S01E01.720p.Proper-FlexGet'}
          
          proper_timeframe_1:
            mock:
              - {title: 'TFTest.S01E01.720p-FlexGet'}
              
          proper_timeframe_2:
            mock:
              - {title: 'TFTest.S01E01.720p.proper-FlexGet'}
        
          no_propers_1:
            mock:
              - {title: 'NoTest.S01E01.720p-FlexGet'}
              
          no_propers_2:
            mock:
              - {title: 'NoTest.S01E01.720p.proper-FlexGet'}
                
              
        """
    
    def test_propers_timeframe(self):
        """Series plugin: propers timeframe"""    
        self.execute_feed('proper_timeframe_1')
        assert self.feed.find_entry('accepted', title='TFTest.S01E01.720p-FlexGet'), \
            'Did not accept before timeframe'
        
        # let 6 hours pass
        age_series(hours=6)
        
        self.execute_feed('proper_timeframe_2')
        assert self.feed.find_entry('rejected', title='TFTest.S01E01.720p.proper-FlexGet'), \
            'Did not reject after proper timeframe'
 
    def test_no_propers(self):
        """Series plugin: no propers at all"""
        self.execute_feed('no_propers_1')
        assert len(self.feed.accepted) == 1, 'broken badly'
        self.execute_feed('no_propers_2')
        assert len(self.feed.rejected) == 1, 'accepted proper'

    def test_min_max_propers(self):
        """Series plugin: min max propers"""
        self.execute_feed('min_max_quality_1')
        assert len(self.feed.accepted) == 1, 'uhh, broken badly'
        self.execute_feed('min_max_quality_2')
        assert len(self.feed.accepted) == 1, 'should have accepted proper'

    def test_lot_propers(self):
        """Series plugin: proper flood"""
        self.execute_feed('lot_propers')
        assert len(self.feed.accepted) == 1, 'should have accepted (only) one of the propers'

    def test_diff_quality_propers(self):
        """Series plugin: proper in different/wrong quality"""
        self.execute_feed('diff_quality_1')
        assert len(self.feed.accepted) == 1
        self.execute_feed('diff_quality_2')
        assert len(self.feed.accepted) == 0, 'should not have accepted lower quality proper'

    def test_propers(self):
        """Series plugin: proper accepted after episode is downloaded"""
        # start with normal download ...
        self.execute_feed('propers_1')
        assert self.feed.find_entry('accepted', title='Test.S01E01.720p-FlexGet'), \
            'Test.S01E01-FlexGet should have been accepted'

        # rejects downloaded
        self.execute_feed('propers_1')
        assert self.feed.find_entry('rejected', title='Test.S01E01.720p-FlexGet'), \
            'Test.S01E01-FlexGet should have been rejected'

        # accepts proper
        self.execute_feed('propers_2')
        assert self.feed.find_entry('accepted', title='Test.S01E01.720p.Proper-FlexGet'), \
            'new undownloaded proper should have been accepted'

        # reject downloaded proper
        self.execute_feed('propers_2')
        assert self.feed.find_entry('rejected', title='Test.S01E01.720p.Proper-FlexGet'), \
            'downloaded proper should have been rejected'

        # reject episode that has been downloaded normally and with proper
        self.execute_feed('propers_3')
        assert self.feed.find_entry('rejected', title='Test.S01E01.FlexGet'), \
            'Test.S01E01.FlexGet should have been rejected'

    def test_proper_available(self):
        """Series plugin: proper available immediately"""
        self.execute_feed('proper_at_first')
        assert self.feed.find_entry('accepted', title='Foobar.S01E01.720p.proper.FlexGet'), \
            'Foobar.S01E01.720p.proper.FlexGet should have been accepted'


class TestSimilarNames(FlexGetBase):

    # hmm, not very good way to test this .. seriesparser should be tested alone?

    __yaml__ = """
        feeds:
          test:
            mock:
              - {title: 'FooBar.S03E01.DSR-FlexGet'}
              - {title: 'FooBar: FirstAlt.S02E01.DSR-FlexGet'}
              - {title: 'FooBar: SecondAlt.S01E01.DSR-FlexGet'}
            series:
              - FooBar
              - 'FooBar: FirstAlt'
              - 'FooBar: SecondAlt'
    """

    def setup(self):
        FlexGetBase.setup(self)
        self.execute_feed('test')

    def test_names(self):
        """Series plugin: similar namings"""
        assert self.feed.find_entry('accepted', title='FooBar.S03E01.DSR-FlexGet'), 'Standard failed?'
        assert self.feed.find_entry('accepted', title='FooBar: FirstAlt.S02E01.DSR-FlexGet'), 'FirstAlt failed'
        assert self.feed.find_entry('accepted', title='FooBar: SecondAlt.S01E01.DSR-FlexGet'), 'SecondAlt failed'


class TestDuplicates(FlexGetBase):

    __yaml__ = """

        presets:
          global: # just cleans log a bit ..
            disable_builtins:
              - seen

        feeds:
          test_dupes:
            mock:
              - {title: 'Foo.2009.S02E04.HDTV.XviD-2HD[FlexGet]'}
              - {title: 'Foo.2009.S02E04.HDTV.XviD-2HD[ASDF]'}
            series:
              - Foo 2009

          test_1:
            mock:
              - {title: 'Foo.Bar.S02E04.HDTV.XviD-2HD[FlexGet]'}
              - {title: 'Foo.Bar.S02E04.HDTV.XviD-2HD[ASDF]'}
            series:
              - foo bar

          test_2:
            mock:
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
            mock:
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
        presets:
          global:
            disable_builtins: yes
            series:
              - FooBar:
                  qualities:
                    - SDTV
                    - 720p
                    - 1080p
        feeds:
          test_1:
            mock:
              - {title: 'FooBar.S01E01.PDTV-FlexGet'}
              - {title: 'FooBar.S01E01.1080p-FlexGet'}
              - {title: 'FooBar.S01E01.HR-FlexGet'}
          test_2:
            mock:
              - {title: 'FooBar.S01E01.720p-FlexGet'}

          propers_1:
            mock:
              - {title: 'FooBar.S01E02.720p-FlexGet'}
          propers_2:
            mock:
              - {title: 'FooBar.S01E02.720p.Proper-FlexGet'}
    """

    def test_qualities(self):
        """Series plugin: qualities"""
        self.execute_feed('test_1')

        assert self.feed.find_entry('accepted', title='FooBar.S01E01.PDTV-FlexGet'), \
            'Didn''t accept FooBar.S01E01.PDTV-FlexGet'
        assert self.feed.find_entry('accepted', title='FooBar.S01E01.1080p-FlexGet'), \
            'Didn''t accept FooBar.S01E01.1080p-FlexGet'

        assert not self.feed.find_entry('accepted', title='FooBar.S01E01.HR-FlexGet'), \
            'Accepted FooBar.S01E01.HR-FlexGet'

        self.execute_feed('test_2')

        assert self.feed.find_entry('accepted', title='FooBar.S01E01.720p-FlexGet'), \
            'Didn''t accept FooBar.S01E01.720p-FlexGet'

        # test that it rejects them afterwards

        self.execute_feed('test_1')

        assert self.feed.find_entry('rejected', title='FooBar.S01E01.PDTV-FlexGet'), \
            'Didn''t rehect FooBar.S01E01.PDTV-FlexGet'
        assert self.feed.find_entry('rejected', title='FooBar.S01E01.1080p-FlexGet'), \
            'Didn''t reject FooBar.S01E01.1080p-FlexGet'

        assert not self.feed.find_entry('accepted', title='FooBar.S01E01.HR-FlexGet'), \
            'Accepted FooBar.S01E01.HR-FlexGet'

    def test_propers(self):
        """Series plugin: qualities + propers"""
        self.execute_feed('propers_1')
        assert self.feed.accepted
        self.execute_feed('propers_2')
        assert self.feed.accepted, 'proper not accepted'
        self.execute_feed('propers_2')
        assert not self.feed.accepted, 'proper accepted again'


class TestIdioticNumbering(FlexGetBase):

    __yaml__ = """
        presets:
          global:
            series:
              - FooBar

        feeds:
          test_1:
            mock:
              - {title: 'FooBar.S01E01.PDTV-FlexGet'}
          test_2:
            mock:
              - {title: 'FooBar.102.PDTV-FlexGet'}
    """

    def test_idiotic(self):
        """Series plugin: idiotic numbering scheme DISABLED"""
        return
        
        self.execute_feed('test_1')
        self.execute_feed('test_2')
        entry = self.feed.find_entry(title='FooBar.102.PDTV-FlexGet')
        assert entry, 'entry not found?'
        assert entry['series_season'] == 1, 'season not detected'
        assert entry['series_episode'] == 2, 'episode not detected'


class TestCapitalization(FlexGetBase):

    __yaml__ = """
        feeds:
          test_1:
            mock:
              - {title: 'FooBar.S01E01.PDTV-FlexGet'}
            series:
              - FOOBAR
          test_2:
            mock:
              - {title: 'FooBar.S01E01.PDTV-FlexGet'}
            series:
              - foobar
    """

    def test_capitalization(self):
        """Series plugin: configuration capitalization"""
        self.execute_feed('test_1')
        assert self.feed.find_entry('accepted', title='FooBar.S01E01.PDTV-FlexGet')
        self.execute_feed('test_2')
        assert self.feed.find_entry('rejected', title='FooBar.S01E01.PDTV-FlexGet')


class TestMixedNumbering(FlexGetBase):

    __yaml__ = """
        presets:
          global:
            series:
              - FooBar

        feeds:
          test_1:
            mock:
              - {title: 'FooBar.S03E07.PDTV-FlexGet'}
          test_2:
            mock:
              - {title: 'FooBar.0307.PDTV-FlexGet'}
    """

    def test_mixednumbering(self):
        """Series plugin: Mixed series numbering - DISABLED!"""
        return
        
        self.execute_feed('test_1')
        assert self.feed.find_entry('accepted', title='FooBar.S03E07.PDTV-FlexGet')
        self.execute_feed('test_2')
        assert self.feed.find_entry('rejected', title='FooBar.0307.PDTV-FlexGet')


class TestAutoExact(FlexGetBase):

    __yaml__ = """
        feeds:
          test:
            mock:
              - {title: 'ABC.MIAMI.S01E01.PDTV-FlexGet'}
              - {title: 'ABC.S01E01.PDTV-FlexGet'}
              - {title: 'ABC.LA.S01E01.PDTV-FlexGet'}
            series:
              - ABC
              - ABC LA
              - ABC Miami
    """

    def test_auto(self):
        """Series plugin: auto enable exact"""
        self.execute_feed('test')
        assert self.feed.find_entry('accepted', title='ABC.S01E01.PDTV-FlexGet')
        assert self.feed.find_entry('accepted', title='ABC.LA.S01E01.PDTV-FlexGet')
        assert self.feed.find_entry('accepted', title='ABC.MIAMI.S01E01.PDTV-FlexGet')


class TestTimeframe(FlexGetBase):

    __yaml__ = """
        presets:
          global:
            series:
              - test:
                  timeframe: 5 hours
                  quality: 720p
        feeds:
          test_no_waiting:
            mock:
              - {title: 'Test.S01E01.720p-FlexGet'}

          test_stop_waiting_1:
            mock:
              - {title: 'Test.S01E02.HDTV-FlexGet'}

          test_stop_waiting_2:
             mock:
               - {title: 'Test.S01E02.720p-FlexGet'}

          test_proper_afterwards:
             mock:
               - {title: 'Test.S01E02.720p.Proper-FlexGet'}

          test_expires:
            mock:
              - {title: 'Test.S01E03.pdtv-FlexGet'}
    """

    def test_no_waiting(self):
        """Series plugin: no timeframe waiting needed"""
        self.execute_feed('test_no_waiting')
        assert self.feed.find_entry('accepted', title='Test.S01E01.720p-FlexGet'), \
            '720p not accepted immediattely'

    def test_stop_waiting(self):
        """Series plugin: timeframe quality appears, stop waiting, proper appears"""
        self.execute_feed('test_stop_waiting_1')
        assert self.feed.rejected
        self.execute_feed('test_stop_waiting_2')
        assert self.feed.find_entry('accepted', title='Test.S01E02.720p-FlexGet'), \
            '720p should have caused stop waiting'
        self.execute_feed('test_proper_afterwards')
        assert self.feed.find_entry('accepted', title='Test.S01E02.720p.Proper-FlexGet'), \
            'proper should have been accepted'

    def test_expires(self):
        """Series plugin: timeframe expires"""
        # first excecution should not accept anything
        self.execute_feed('test_expires')
        assert not self.feed.accepted

        # let 3 hours pass
        age_series(hours=3)
        self.execute_feed('test_expires')
        assert not self.feed.accepted, 'expired too soon'

        # let another 3 hours pass, should expire now!
        age_series(hours=6)
        self.execute_feed('test_expires')
        assert self.feed.accepted, 'timeframe didn\'t expire'


class TestBacklog(FlexGetBase):

    __yaml__ = """
        feeds:
          backlog:
            mock:
              - {title: 'Test.S01E01.hdtv-FlexGet'}
            series:
              - test: {timeframe: 6 hours}
    """

    def testBacklog(self):
        """Series plugin: backlog"""
        self.execute_feed('backlog')
        assert self.feed.rejected, 'no entries at the start'
        # simulate test going away from the feed
        del(self.manager.config['feeds']['backlog']['mock'])
        age_series(hours=12)
        self.execute_feed('backlog')
        assert self.feed.accepted, 'backlog is not injecting episodes'


class TestManipulate(FlexGetBase):

    """Tests that it's possible to manipulate entries before they're parsed by series plugin"""

    __yaml__ = """
        feeds:
          test_1:
            mock:
              - {title: 'PREFIX: Test.S01E01.hdtv-FlexGet'}
            series:
              - test
          test_2:
            mock:
              - {title: 'PREFIX: Test.S01E01.hdtv-FlexGet'}
            series:
              - test
            manipulate:
              - title:
                  extract: '^PREFIX: (.*)'
    """

    def testManipulate(self):
        """Series plugin: test manipulation priority"""
        # should not work with the prefix
        self.execute_feed('test_1')
        assert not self.feed.accepted, 'series accepted even with prefix?'
        assert not self.feed.accepted, 'series rejecte even with prefix?'
        self.execute_feed('test_2')
        assert self.feed.accepted, 'manipulate failed to pre-clean title'


class TestFromGroup(FlexGetBase):

    __yaml__ = """
        feeds:
          test:
            mock:
              - {title: '[Ignored] Test 12'}
              - {title: '[FlexGet] Test 12'}
              - {title: 'Test.13.HDTV-Ignored'}
              - {title: 'Test.13.HDTV-FlexGet'}
              - {title: 'Test.14.HDTV-Name'}
            series:
              - test: {from_group: [Name, FlexGet]}
    """

    def testFromGroup(self):
        """Series plugin: test from_group"""
        self.execute_feed('test')
        assert self.feed.find_entry('accepted', title='[FlexGet] Test 12')
        assert self.feed.find_entry('accepted', title='Test.13.HDTV-FlexGet')
        assert self.feed.find_entry('accepted', title='Test.14.HDTV-Name')


class TestSeriesPremiere(FlexGetBase):

    __yaml__ = """
        presets:
          global:
            metainfo_series: yes
            series_premiere: yes
        feeds:
          test:
            mock:
              - {title: 'FooBar.S01E01.PDTV-FlexGet'}
              - {title: 'FooBar.S01E11.1080p-FlexGet'}
              - {title: 'FooBar.S02E02.HR-FlexGet'}
    """
      
    def testOnlyPremieres(self):
        """Test series premiere"""
        self.execute_feed('test')
        assert self.feed.find_entry('accepted', title='FooBar.S01E01.PDTV-FlexGet', \
            series_name='FooBar', series_season=1, series_episode=1), 'Series premiere should have been accepted'
        assert len(self.feed.accepted) == 1
    # TODO: Add more tests, test interaction with series plugin and series_exists
