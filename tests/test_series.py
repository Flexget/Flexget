from tests import FlexGetBase


def age_series(**kwargs):
    from flexget.plugins.filter.series import Release
    from flexget.manager import Session
    import datetime
    session = Session()
    session.query(Release).update({'first_seen': datetime.datetime.now() - datetime.timedelta(**kwargs)})
    session.commit()


class TestQuality(FlexGetBase):

    __yaml__ = """
        feeds:
          exact_quality:
            mock:
              - {title: 'QTest.S01E01.HDTV.XViD-FlexGet'}
              - {title: 'QTest.S01E01.PDTV.XViD-FlexGet'}
              - {title: 'QTest.S01E01.DSR.XViD-FlexGet'}
              - {title: 'QTest.S01E01.1080p.XViD-FlexGet'}
              - {title: 'QTest.S01E01.720p.XViD-FlexGet'}
            series:
              - QTest:
                  quality: 720p

          quality_fail:
            mock:
              - {title: 'Q2Test.S01E01.HDTV.XViD-FlexGet'}
              - {title: 'Q2Test.S01E01.PDTV.XViD-FlexGet'}
              - {title: 'Q2Test.S01E01.DSR.XViD-FlexGet'}
            series:
              - Q2Test:
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
                  quality: ">720p"

          max_quality:
            mock:
              - {title: 'MaxQTest.S01E01.HDTV.XViD-FlexGet'}
              - {title: 'MaxQTest.S01E01.PDTV.XViD-FlexGet'}
              - {title: 'MaxQTest.S01E01.DSR.XViD-FlexGet'}
              - {title: 'MaxQTest.S01E01.1080p.XViD-FlexGet'}
              - {title: 'MaxQTest.S01E01.720p.XViD-FlexGet'}
              - {title: 'MaxQTest.S01E01.720p.bluray-FlexGet'}
            series:
              - MaxQTest:
                  quality: "<720p <=HDTV"

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
                  quality: 480p-hr

          max_unknown_quality:
            mock:
              - {title: 'MaxUnknownQTest.S01E01.XViD-FlexGet'}
            series:
              - MaxUnknownQTest:
                  quality: "<=hdtv"

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

    def test_exact_quality(self):
        """Series plugin: choose by quality"""
        self.execute_feed('exact_quality')
        assert self.feed.find_entry('accepted', title='QTest.S01E01.720p.XViD-FlexGet'), \
            '720p should have been accepted'
        assert len(self.feed.accepted) == 1, 'should have accepted only one'

    def test_quality_fail(self):
        self.execute_feed('quality_fail')
        assert not self.feed.accepted, 'No qualities should have matched'

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
              - {title: 'Date.Series.10.14.09.XViD'}
              - {title: 'Date Series 2010 11 17 XViD'}
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
            metainfo_series: yes
            mock:
              - {title: 'Test.Series.with.extra.crap.S01E02.PDTV.XViD-FlexGet'}
              - {title: 'Other.Show.with.extra.crap.S02E01.PDTV.XViD-FlexGet'}
            series:
              - Test Series

          test_all_series_mode:
            mock:
              - {title: 'Test.Series.S01E02.PDTV.XViD-FlexGet'}
              - {title: 'Test Series - 1x03 - PDTV XViD-FlexGet'}
              - {title: 'Other.Show.S02E01.PDTV.XViD-FlexGet'}
              - {title: 'other show season 2 episode 2'}
              - {title: 'Date.Show.03-29-2012.HDTV.XViD-FlexGet'}
            all_series: yes
    """

    def test_smoke(self):
        """Series plugin: test several standard features"""
        self.execute_feed('test')

        # normal passing
        assert self.feed.find_entry(title='Another.Series.S01E20.720p.XViD-FlexGet'), \
            'Another.Series.S01E20.720p.XViD-FlexGet should have passed'

        # date formats
        df = ['Date.Series.10-11-2008.XViD', 'Date.Series.10.12.2008.XViD', 'Date Series 2010 11 17 XViD',
              'Date.Series.2008-10-13.XViD', 'Date.Series.10.14.09.XViD']
        for d in df:
            entry = self.feed.find_entry(title=d)
            assert entry, 'Date format did not match %s' % d
            assert 'series_parser' in entry, 'series_parser missing from %s' % d
            assert entry['series_parser'].id_type == 'date', '%s did not return three groups for dates' % d

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
        assert entry['series_name'] == entry['series_parser'].name == 'Other Show With Extra Crap', \
            'metainfo_series is not running'
        # Make sure the good series data overrode metainfo data for the listed series
        entry = self.feed.find_entry('accepted', title='Test.Series.with.extra.crap.S01E02.PDTV.XViD-FlexGet')
        assert not entry.get('series_guessed'), 'series plugin should override series_guessed'
        assert entry['series_name'] == entry['series_parser'].name == 'Test Series', \
            'Series name should be \'Test Series\', was: entry: %s, parser: %s' % (entry['series_name'], entry['series_parser'].name)

    def test_all_series_mode(self):
        """Series plugin: test all option"""
        self.execute_feed('test_all_series_mode')
        assert self.feed.find_entry('accepted', title='Test.Series.S01E02.PDTV.XViD-FlexGet')
        entry = self.feed.find_entry('accepted', title='Test Series - 1x03 - PDTV XViD-FlexGet')
        assert entry['series_name'] == 'Test Series'
        entry = self.feed.find_entry('accepted', title='Other.Show.S02E01.PDTV.XViD-FlexGet')
        assert entry['series_guessed']
        entry2 = self.feed.find_entry('accepted', title='other show season 2 episode 2')
        # Make sure case is normalized so series are marked with the same name no matter the case in the title
        assert entry['series_name'] == entry2['series_name'] == 'Other Show', 'Series names should be in title case'
        entry = self.feed.find_entry('accepted', title='Date.Show.03-29-2012.HDTV.XViD-FlexGet')
        assert entry['series_guessed']
        assert entry['series_name'] == 'Date Show'


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

          test_seq1:
            mock:
              - title: seq 05
            series:
              - seq
          test_seq2:
            mock:
              - title: seq 06
            series:
              - seq
          test_seq3:
            mock:
              - title: seq 10
            series:
              - seq
          test_seq4:
            mock:
              - title: seq 01
            series:
              - seq

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

    def test_sequence(self):
        # First should be accepted
        self.execute_feed('test_seq1')
        entry = self.feed.find_entry('accepted', title='seq 05')
        assert entry['series_id'] == 5

        # Next in sequence should be accepted
        self.execute_feed('test_seq2')
        entry = self.feed.find_entry('accepted', title='seq 06')
        assert entry['series_id'] == 6

        # Should be too far in the future
        self.execute_feed('test_seq3')
        entry = self.feed.find_entry(title='seq 10')
        assert entry not in self.feed.accepted, 'Should have been too far in future'

        # Should be too far in the past
        self.execute_feed('test_seq4')
        entry = self.feed.find_entry(title='seq 01')
        assert entry not in self.feed.accepted, 'Should have been too far in the past'


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
                  quality: HR-1080p
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

          proper_upgrade_1:
            mock:
              - {title: 'Test.S02E01.hdtv.proper'}

          proper_upgrade_2:
            mock:
              - {title: 'Test.S02E01.hdtv.real.proper'}
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

    def test_proper_upgrade(self):
        """Series plugin: real proper after proper"""
        self.execute_feed('proper_upgrade_1')
        assert self.feed.find_entry('accepted', title='Test.S02E01.hdtv.proper')
        self.execute_feed('proper_upgrade_2')
        assert self.feed.find_entry('accepted', title='Test.S02E01.hdtv.real.proper')


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
              - FooBaz:
                  upgrade: yes
                  qualities:
                    - hdtv
                    - hr
                    - 720p
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

          upgrade_1:
            mock:
              - {title: 'FooBaz.S01E02.pdtv-FlexGet'}
              - {title: 'FooBaz.S01E02.HR-FlexGet'}

          upgrade_2:
            mock:
              - {title: 'FooBaz.S01E02.720p-FlexGet'}
              - {title: 'FooBaz.S01E02.1080p-FlexGet'}

          upgrade_3:
            mock:
              - {title: 'FooBaz.S01E02.hdtv-FlexGet'}
              - {title: 'FooBaz.S01E02.720p rc-FlexGet'}
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
            'Didn\'t reject FooBar.S01E01.PDTV-FlexGet'
        assert self.feed.find_entry('rejected', title='FooBar.S01E01.1080p-FlexGet'), \
            'Didn\'t reject FooBar.S01E01.1080p-FlexGet'

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

    def test_qualities_upgrade(self):
        self.execute_feed('upgrade_1')
        assert self.feed.find_entry('accepted', title='FooBaz.S01E02.HR-FlexGet'), 'HR quality should be accepted'
        assert len(self.feed.accepted) == 1, 'Only best quality should be accepted'
        self.execute_feed('upgrade_2')
        assert self.feed.find_entry('accepted', title='FooBaz.S01E02.720p-FlexGet'), '720p quality should be accepted'
        assert len(self.feed.accepted) == 1, 'Only best quality should be accepted'
        self.execute_feed('upgrade_3')
        assert not self.feed.accepted, 'Should not have accepted worse qualities'


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


class TestExact(FlexGetBase):

    __yaml__ = """
        feeds:
          auto:
            mock:
              - {title: 'ABC.MIAMI.S01E01.PDTV-FlexGet'}
              - {title: 'ABC.S01E01.PDTV-FlexGet'}
              - {title: 'ABC.LA.S01E01.PDTV-FlexGet'}
            series:
              - ABC
              - ABC LA
              - ABC Miami
          name_regexp:
            mock:
              - title: show s09e05 hdtv
              - title: show a s09e06 hdtv
            series:
              - show:
                  name_regexp: ^show
                  exact: yes
          date:
            mock:
              - title: date show 04.01.2011 hdtv
              - title: date show b 04.02.2011 hdtv
            series:
              - date show:
                  exact: yes
    """

    def test_auto(self):
        """Series plugin: auto enable exact"""
        self.execute_feed('auto')
        assert self.feed.find_entry('accepted', title='ABC.S01E01.PDTV-FlexGet')
        assert self.feed.find_entry('accepted', title='ABC.LA.S01E01.PDTV-FlexGet')
        assert self.feed.find_entry('accepted', title='ABC.MIAMI.S01E01.PDTV-FlexGet')

    def test_with_name_regexp(self):
        self.execute_feed('name_regexp')
        assert self.feed.find_entry('accepted', title='show s09e05 hdtv')
        assert not self.feed.find_entry('accepted', title='show a s09e06 hdtv')

    def test_dated_show(self):
        self.execute_feed('date')
        assert self.feed.find_entry('accepted', title='date show 04.01.2011 hdtv')
        assert not self.feed.find_entry('accepted', title='date show b 04.02.2011 hdtv')

class TestTimeframe(FlexGetBase):

    __yaml__ = """
        presets:
          global:
            series:
              - test:
                  timeframe: 5 hours
                  enough: 720p
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

          test_min_max_fail:
            series:
              - mm test:
                  timeframe: 5 hours
                  enough: 720p
                  quality: hdtv+ <=720p
            mock:
              - {title: 'MM Test.S01E02.pdtv-FlexGet'}
              - {title: 'MM Test.S01E02.1080p-FlexGet'}

          test_min_max_pass:
            series:
              - mm test:
                  timeframe: 5 hours
                  enough: 720p
                  quality: hdtv+ <=720p
            mock:
              - {title: 'MM Test.S01E02.pdtv-FlexGet'}
              - {title: 'MM Test.S01E02.hdtv-FlexGet'}
              - {title: 'MM Test.S01E02.1080p-FlexGet'}

          test_qualities_fail:
            series:
              - q test:
                  timeframe: 5 hours
                  qualities:
                    - hdtv
                    - 1080p

            mock:
              - {title: 'Q Test.S01E02.pdtv-FlexGet'}
              - {title: 'Q Test.S01E02.1080p-FlexGet'}

          test_qualities_pass:
            series:
              - q test:
                  timeframe: 5 hours
                  qualities:
                    - sdtv
                    - 720p

            mock:
              - {title: 'Q Test.S01E02.hdtv-FlexGet'}
              - {title: 'Q Test.S01E02.1080p-FlexGet'}

    """

    def test_no_waiting(self):
        """Series plugin: no timeframe waiting needed"""
        self.execute_feed('test_no_waiting')
        assert self.feed.find_entry('accepted', title='Test.S01E01.720p-FlexGet'), \
            '720p not accepted immediattely'

    def test_stop_waiting(self):
        """Series plugin: timeframe quality appears, stop waiting, proper appears"""
        self.execute_feed('test_stop_waiting_1')
        assert self.feed.entries and not self.feed.accepted
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

    def test_min_max_fail(self):
        self.execute_feed('test_min_max_fail')
        assert not self.feed.accepted

        # Let 6 hours pass, timeframe should not even been started, as pdtv doesn't meet min_quality
        age_series(hours=6)
        self.execute_feed('test_min_max_fail')
        assert self.feed.entries and not self.feed.accepted

    def test_min_max_pass(self):
        self.execute_feed('test_min_max_pass')
        assert not self.feed.accepted

        # Let 6 hours pass, timeframe should expire and accept hdtv copy
        age_series(hours=6)
        self.execute_feed('test_min_max_pass')
        assert self.feed.find_entry('accepted', title='MM Test.S01E02.hdtv-FlexGet')
        assert len(self.feed.accepted) == 1

    def test_qualities_fail(self):
        self.execute_feed('test_qualities_fail')
        assert self.feed.find_entry('accepted', title='Q Test.S01E02.1080p-FlexGet'),\
            'should have accepted wanted quality'
        assert len(self.feed.accepted) == 1

        # Let 6 hours pass, timeframe should not even been started, as we already have one of our qualities
        age_series(hours=6)
        self.execute_feed('test_qualities_fail')
        assert self.feed.entries and not self.feed.accepted

    def test_qualities_pass(self):
        self.execute_feed('test_qualities_pass')
        assert not self.feed.accepted, 'None of the qualities should have matched'

        # Let 6 hours pass, timeframe should expire and accept 1080p copy
        age_series(hours=6)
        self.execute_feed('test_qualities_pass')
        assert self.feed.find_entry('accepted', title='Q Test.S01E02.1080p-FlexGet')
        assert len(self.feed.accepted) == 1


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
        assert self.feed.entries and not self.feed.accepted, 'no entries at the start'
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


class TestWatched(FlexGetBase):

    __yaml__ = """
        presets:
          global:
            mock:
              - {title: 'WTest.S02E03.HDTV.XViD-FlexGet'}
              - {title: 'W2Test.S02E03.HDTV.XViD-FlexGet'}
        feeds:
          watched_test:
            series:
              - WTest:
                  watched: S02E04
              - W2Test:
                  watched:
                    season: 3
                    episode: 1
          unwatched_test:
            series:
              - WTest:
                  watched: s02e02
              - W2Test:
                  watched:
                    season: 1
                    episode: 3
    """

    def test_watched(self):
        self.execute_feed('watched_test')
        assert not self.feed.accepted, 'No entries should have been accepted, as they have been watched'

    def test_unwatched(self):
        self.execute_feed('unwatched_test')
        assert len(self.feed.accepted) == 2, 'Entries should have been accepted, they are after the watched episode'


class TestSeriesPremiere(FlexGetBase):

    __yaml__ = """
        presets:
          global:
            metainfo_series: yes
            series_premiere: yes
        feeds:
          test:
            mock:
              - {title: 'Foobar.S01E01.PDTV-FlexGet'}
              - {title: 'Foobar.S01E11.1080p-FlexGet'}
              - {title: 'Foobar.S02E02.HR-FlexGet'}
    """

    def testOnlyPremieres(self):
        """Test series premiere"""
        self.execute_feed('test')
        assert self.feed.find_entry('accepted', title='Foobar.S01E01.PDTV-FlexGet',
            series_name='Foobar', series_season=1, series_episode=1), 'Series premiere should have been accepted'
        assert len(self.feed.accepted) == 1
    # TODO: Add more tests, test interaction with series plugin and series_exists


class TestImportSeries(FlexGetBase):

    __yaml__ = """
        feeds:
          timeframe_max:
            import_series:
              settings:
                propers: 12 hours
                enough: 720p
                timeframe: 5 minutes
                quality: "<=720p <=bluray"
              from:
                mock:
                  - title: the show
            mock:
              - title: the show s03e02 1080p bluray
              - title: the show s03e02 hdtv
    """

    def test_timeframe_max(self):
        """Tests import_series as well as timeframe with max_quality."""
        self.execute_feed('timeframe_max')
        assert not self.feed.accepted, 'Entry shouldnot have been accepted on first run.'
        age_series(minutes=6)
        self.execute_feed('timeframe_max')
        assert self.feed.find_entry('accepted', title='the show s03e02 hdtv'), \
                'hdtv should have been accepted after timeframe.'


class TestIDTypes(FlexGetBase):

    __yaml__ = """
        feeds:
          all_types:
            series:
              - episode
              - date
              - sequence
              - stupid id
            mock:
              - title: episode S03E04
              - title: episode 3x05
              - title: date 2011.4.3 other crap hdtv
              - title: date 4.5.11
              - title: sequence 003
              - title: sequence 4
              - title: stupid id 2008x3.5
    """

    def test_id_types(self):
        self.execute_feed('all_types')
        for entry in self.feed.entries:
            assert entry['series_name'], '%s not parsed by series plugin' % entry['title']
            assert entry['series_id_type'] in entry['series_name']


class TestCaseChange(FlexGetBase):

    __yaml__ = """
        feeds:
          first:
            mock:
              - title: theshow s02e04
            series:
              - TheShow
          second:
            mock:
              - title: thEshoW s02e04 other
            series:
              - THESHOW
    """

    def test_case_change(self):
        self.execute_feed('first')
        # Make sure series_name uses case from config, make sure episode is accepted
        assert self.feed.find_entry('accepted', title='theshow s02e04', series_name='TheShow')
        self.execute_feed('second')
        # Make sure series_name uses new case from config, make sure ep is rejected because we have a copy
        assert self.feed.find_entry('rejected', title='thEshoW s02e04 other', series_name='THESHOW')


class TestInvalidSeries(FlexGetBase):

    __yaml__ = """
        feeds:
          blank:
            mock:
              - title: whatever
            series:
              - '':
                  quality: 720p
    """

    def test_blank_series(self):
        """Make sure a blank series doesn't crash."""
        self.execute_feed('blank')
        assert not self.feed._abort, 'Feed should not have aborted'


class TestDoubleEps(FlexGetBase):

    __yaml__ = """
        feeds:
          test_double1:
            mock:
              - title: double S01E02-E03
            series:
              - double
          test_double2:
            mock:
              - title: double S01E03
            series:
              - double

          test_double_prefered:
            mock:
              - title: double S02E03
              - title: double S02E03-04
            series:
              - double
    """

    def test_double(self):
        # First should be accepted
        self.execute_feed('test_double1')
        assert self.feed.find_entry('accepted', title='double S01E02-E03')

        # We already got ep 3 as part of double, should not be accepted
        self.execute_feed('test_double2')
        assert not self.feed.find_entry('accepted', title='double S01E03')

    def test_double_prefered(self):
        # Given a choice of single or double ep at same quality, grab the double
        self.execute_feed('test_double_prefered')
        assert self.feed.find_entry('accepted', title='double S02E03-04')
        assert not self.feed.find_entry('accepted', title='S02E03')
