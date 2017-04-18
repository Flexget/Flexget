from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from io import StringIO

import pytest
from jinja2 import Template

from flexget.entry import Entry
from flexget.logger import capture_output
from flexget.manager import get_parser
from flexget.task import TaskAbort


def age_series(**kwargs):
    from flexget.plugins.filter.series import EpisodeRelease
    from flexget.manager import Session
    import datetime
    session = Session()
    session.query(EpisodeRelease).update({'first_seen': datetime.datetime.now() - datetime.timedelta(**kwargs)})
    session.commit()


@pytest.fixture(scope='class', params=['internal', 'guessit'], ids=['internal', 'guessit'], autouse=True)
def config(request):
    """Override and parametrize default config fixture for all series tests."""
    newconfig = Template(request.cls.config).render({'parser': request.param})
    # Make sure we remembered to put the section in config
    assert request.cls.config != newconfig, 'config parameterization did nothing?'
    return newconfig


class TestQuality(object):
    config = """
        templates:
          global:
            parsing:
              series: {{parser}}
        tasks:
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

          quality_from_group:
            mock:
              - {title: 'GroupQual.S01E01.HDTV.XViD-FlexGet'}
              - {title: 'GroupQual.S01E01.PDTV.XViD-FlexGet'}
              - {title: 'GroupQual.S01E01.DSR.XViD-FlexGet'}
              - {title: 'GroupQual.S01E01.1080p.XViD-FlexGet'}
              - {title: 'GroupQual.S01E01.720p.XViD-FlexGet'}
              - {title: 'Other.S01E01.hdtv.dd5.1.XViD-FlexGet'}
              - {title: 'Other.S01E01.720p.hdtv.XViD-FlexGet'}
            series:
              720P:
                - GroupQual
              # Test that an integer group name doesn't cause an exception.
              1080:
                - Test
              hdtv <hr !dd5.1:
                - Other
          quality_in_series_name:
            mock:
            - title: my 720p show S01E01
            - title: my 720p show S01E02 720p
            series:
            - my 720p show:
                quality: '<720p'
    """

    def test_exact_quality(self, execute_task):
        """Series plugin: choose by quality"""
        task = execute_task('exact_quality')
        assert task.find_entry('accepted', title='QTest.S01E01.720p.XViD-FlexGet'), \
            '720p should have been accepted'
        assert len(task.accepted) == 1, 'should have accepted only one'

    def test_quality_fail(self, execute_task):
        task = execute_task('quality_fail')
        assert not task.accepted, 'No qualities should have matched'

    def test_min_quality(self, execute_task):
        """Series plugin: min_quality"""
        task = execute_task('min_quality')
        assert task.find_entry('accepted', title='MinQTest.S01E01.1080p.XViD-FlexGet'), \
            'MinQTest.S01E01.1080p.XViD-FlexGet should have been accepted'
        assert len(task.accepted) == 1, 'should have accepted only one'

    def test_max_quality(self, execute_task):
        """Series plugin: max_quality"""
        task = execute_task('max_quality')
        assert task.find_entry('accepted', title='MaxQTest.S01E01.HDTV.XViD-FlexGet'), \
            'MaxQTest.S01E01.HDTV.XViD-FlexGet should have been accepted'
        assert len(task.accepted) == 1, 'should have accepted only one'

    def test_min_max_quality(self, execute_task):
        """Series plugin: min_quality with max_quality"""
        task = execute_task('min_max_quality')
        assert task.find_entry('accepted', title='MinMaxQTest.S01E01.HR.XViD-FlexGet'), \
            'MinMaxQTest.S01E01.HR.XViD-FlexGet should have been accepted'
        assert len(task.accepted) == 1, 'should have accepted only one'

    def test_max_unknown_quality(self, execute_task):
        """Series plugin: max quality with unknown quality"""
        task = execute_task('max_unknown_quality')
        assert len(task.accepted) == 1, 'should have accepted'

    def test_group_quality(self, execute_task):
        """Series plugin: quality from group name"""
        task = execute_task('quality_from_group')
        assert task.find_entry('accepted', title='GroupQual.S01E01.720p.XViD-FlexGet'), \
            'GroupQual.S01E01.720p.XViD-FlexGet should have been accepted'
        assert len(task.accepted) == 1, 'should have accepted only one (no entries should pass for series `other`'

    def test_quality_in_series_name(self, execute_task):
        """Make sure quality in title does not get parsed as quality"""
        task = execute_task('quality_in_series_name')
        assert task.find_entry('accepted', title='my 720p show S01E01'), \
            'quality in title should not have been parsed'
        assert len(task.accepted) == 1, 'should not have accepted 720p entry'


class TestDatabase(object):
    config = """
        templates:
          global:
            parsing:
              series: {{parser}}
            series:
              - some series
              - progress

        tasks:
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

    def test_database(self, execute_task):
        """Series plugin: simple database"""

        task = execute_task('test_1')
        task = execute_task('test_2')
        assert task.find_entry('rejected', title='Some.Series.S01E20.720p.XViD-DoppelGanger'), \
            'failed basic download remembering'

    def test_doppelgangers(self, execute_task):
        """Series plugin: doppelganger releases (dupes)"""

        task = execute_task('progress_1')
        assert task.find_entry('accepted', title='Progress.S01E20.720p-FlexGet'), \
            'best quality not accepted'
        # should not accept anything
        task = execute_task('progress_1')
        assert not task.accepted, 'repeated execution accepted'
        # introduce new doppelgangers
        task = execute_task('progress_2')
        assert not task.accepted, 'doppelgangers accepted'


class TestFilterSeries(object):
    config = """
        templates:
          global:
            parsing:
              series: {{parser}}
        tasks:
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

          test_alternate_name:
            mock:
            - title: The.Show.S01E01
            - title: Other.Name.S01E02
            - title: many.names.S01E01
            - title: name.1.S01E02
            - title: name.2.S01E03
            - title: paren.title.2013.S01E01
            series:
            - The Show:
                alternate_name: Other Name
            - many names:
                alternate_name:
                - name 1
                - name 2
            - paren title (US):
                alternate_name: paren title 2013
    """

    def test_smoke(self, execute_task):
        """Series plugin: test several standard features"""
        task = execute_task('test')

        # normal passing
        assert task.find_entry(title='Another.Series.S01E20.720p.XViD-FlexGet'), \
            'Another.Series.S01E20.720p.XViD-FlexGet should have passed'

        # date formats
        df = ['Date.Series.10-11-2008.XViD', 'Date.Series.10.12.2008.XViD', 'Date Series 2010 11 17 XViD',
              'Date.Series.2008-10-13.XViD', 'Date.Series.10.14.09.XViD']
        for d in df:
            entry = task.find_entry(title=d)
            assert entry, 'Date format did not match %s' % d
            assert 'series_parser' in entry, 'series_parser missing from %s' % d
            assert entry['series_parser'].id_type == 'date', '%s did not return three groups for dates' % d

        # parse from filename
        assert task.find_entry(filename='Filename.Series.S01E26.XViD'), 'Filename parsing failed'

        # empty description
        assert task.find_entry(title='Empty.Description.S01E22.XViD'), 'Empty Description failed'

        # chaining with regexp plugin
        assert task.find_entry('rejected', title='Another.Series.S01E21.1080p.H264-FlexGet'), \
            'regexp chaining'

    def test_metainfo_series_override(self, execute_task):
        """Series plugin: override metainfo_series"""
        task = execute_task('metainfo_series_override')
        # Make sure the metainfo_series plugin is working first
        entry = task.find_entry('entries', title='Other.Show.with.extra.crap.S02E01.PDTV.XViD-FlexGet')
        assert entry['series_guessed'], 'series should have been guessed'
        assert entry['series_name'] == entry['series_parser'].name == 'Other Show With Extra Crap', \
            'metainfo_series is not running'
        # Make sure the good series data overrode metainfo data for the listed series
        entry = task.find_entry('accepted', title='Test.Series.with.extra.crap.S01E02.PDTV.XViD-FlexGet')
        assert not entry.get('series_guessed'), 'series plugin should override series_guessed'
        assert entry['series_name'] == entry['series_parser'].name == 'Test Series', \
            'Series name should be \'Test Series\', was: entry: %s, parser: %s' % (
                entry['series_name'], entry['series_parser'].name)

    def test_all_series_mode(self, execute_task):
        """Series plugin: test all option"""
        task = execute_task('test_all_series_mode')
        assert task.find_entry('accepted', title='Test.Series.S01E02.PDTV.XViD-FlexGet')
        task.find_entry('accepted', title='Test Series - 1x03 - PDTV XViD-FlexGet')
        entry = task.find_entry('accepted', title='Test Series - 1x03 - PDTV XViD-FlexGet')
        assert entry
        assert entry.get('series_name') == 'Test Series'
        entry = task.find_entry('accepted', title='Other.Show.S02E01.PDTV.XViD-FlexGet')
        assert entry.get('series_guessed')
        entry2 = task.find_entry('accepted', title='other show season 2 episode 2')
        # Make sure case is normalized so series are marked with the same name no matter the case in the title
        assert entry.get('series_name') == entry2.get(
            'series_name') == 'Other Show', 'Series names should be in title case'
        entry = task.find_entry('accepted', title='Date.Show.03-29-2012.HDTV.XViD-FlexGet')
        assert entry.get('series_guessed')
        assert entry.get('series_name') == 'Date Show'

    def test_alternate_name(self, execute_task):
        task = execute_task('test_alternate_name')
        assert all(e.accepted for e in task.all_entries), 'All releases should have matched a show'


class TestEpisodeAdvancement(object):
    config = """
        templates:
          global:
            parsing:
              series: {{parser}}
        tasks:
          test_backwards_1:
            mock:
              - {title: 'backwards s02e12'}
              - {title: 'backwards s02e10'}
            series:
              - backwards

          test_backwards_2:
            mock:
              - {title: 'backwards s02e01'}
            series:
              - backwards

          test_backwards_3:
            mock:
              - {title: 'backwards s01e01'}
            series:
              - backwards

          test_backwards_okay_1:
            mock:
              - {title: 'backwards s01e02'}
            series:
              - backwards:
                  tracking: backfill

          test_backwards_okay_2:
            mock:
              - {title: 'backwards s01e03'}
            series:
              - backwards:
                  tracking: no

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
              - {title: 'forwards s04e02'}
            series:
              - forwards

          test_forwards_5:
            mock:
              - {title: 'forwards s05e01'}
            series:
              - forwards

          test_forwards_okay_1:
            mock:
              - {title: 'forwards s05e01'}
            series:
              - forwards:
                  tracking: no

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

    def test_backwards(self, execute_task):
        """Series plugin: episode advancement (backwards)"""
        task = execute_task('test_backwards_1')
        assert task.find_entry('accepted', title='backwards s02e12'), \
            'backwards s02e12 should have been accepted'
        assert task.find_entry('accepted', title='backwards s02e10'), \
            'backwards s02e10 should have been accepted within grace margin'
        task = execute_task('test_backwards_2')
        assert task.find_entry('accepted', title='backwards s02e01'), \
            'backwards s02e01 should have been accepted, in current season'
        task = execute_task('test_backwards_3')
        assert task.find_entry('rejected', title='backwards s01e01'), \
            'backwards s01e01 should have been rejected, in previous season'
        task = execute_task('test_backwards_okay_1')
        assert task.find_entry('accepted', title='backwards s01e02'), \
            'backwards s01e01 should have been accepted, backfill enabled'
        task = execute_task('test_backwards_okay_2')
        assert task.find_entry('accepted', title='backwards s01e03'), \
            'backwards s01e01 should have been accepted, tracking off'

    def test_forwards(self, execute_task):
        """Series plugin: episode advancement (future)"""
        task = execute_task('test_forwards_1')
        assert task.find_entry('accepted', title='forwards s01e01'), \
            'forwards s01e01 should have been accepted'
        task = execute_task('test_forwards_2')
        assert task.find_entry('accepted', title='forwards s02e01'), \
            'forwards s02e01 should have been accepted'
        task = execute_task('test_forwards_3')
        assert task.find_entry('accepted', title='forwards s03e01'), \
            'forwards s03e01 should have been accepted'
        task = execute_task('test_forwards_4')
        assert task.find_entry('rejected', title='forwards s04e02'), \
            'forwards s04e02 should have been rejected'
        task = execute_task('test_forwards_5')
        assert task.find_entry('rejected', title='forwards s05e01'), \
            'forwards s05e01 should have been rejected'
        task = execute_task('test_forwards_okay_1')
        assert task.find_entry('accepted', title='forwards s05e01'), \
            'forwards s05e01 should have been accepted with tracking turned off'

    def test_unordered(self, execute_task):
        """Series plugin: unordered episode advancement"""
        task = execute_task('test_unordered')
        assert len(task.accepted) == 12, \
            'not everyone was accepted'

    def test_sequence(self, execute_task):
        # First should be accepted
        task = execute_task('test_seq1')
        entry = task.find_entry('accepted', title='seq 05')
        assert entry['series_id'] == 5

        # Next in sequence should be accepted
        task = execute_task('test_seq2')
        entry = task.find_entry('accepted', title='seq 06')
        assert entry['series_id'] == 6

        # Should be too far in the future
        task = execute_task('test_seq3')
        entry = task.find_entry(title='seq 10')
        assert entry not in task.accepted, 'Should have been too far in future'

        # Should be too far in the past
        task = execute_task('test_seq4')
        entry = task.find_entry(title='seq 01')
        assert entry not in task.accepted, 'Should have been too far in the past'


class TestFilterSeriesPriority(object):
    config = """
        templates:
          global:
            parsing:
              series: {{parser}}
        tasks:
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

    def test_priorities(self, execute_task):
        """Series plugin: regexp plugin is able to reject before series plugin"""
        task = execute_task('test')
        assert task.find_entry('rejected', title='foobar 720p s01e01'), \
            'foobar 720p s01e01 should have been rejected'
        assert task.find_entry('accepted', title='foobar hdtv s01e01'), \
            'foobar hdtv s01e01 is not accepted'


class TestPropers(object):
    config = """
        templates:
          global:
            parsing:
              series: {{parser}}
            # prevents seen from rejecting on second execution,
            # we want to see that series is able to reject
            disable: builtins
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

        tasks:
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

          anime_proper_1:
            mock:
              - title: test 04v0 hdtv

          anime_proper_2:
            mock:
              - title: test 04 hdtv

          fastsub_proper_1:
            mock:
              - title: test s01e01 Fastsub hdtv

          fastsub_proper_2:
               mock:
                 - title: test s01e01 Fastsub repack hdtv

          fastsub_proper_3:
             mock:
              - title: test s01e01 hdtv

          fastsub_proper_4:
            mock:
               - title: test s01e01 proper hdtv
        """

    def test_propers_timeframe(self, execute_task):
        """Series plugin: propers timeframe"""
        task = execute_task('proper_timeframe_1')
        assert task.find_entry('accepted', title='TFTest.S01E01.720p-FlexGet'), \
            'Did not accept before timeframe'

        # let 6 hours pass
        age_series(hours=6)

        task = execute_task('proper_timeframe_2')
        assert task.find_entry('rejected', title='TFTest.S01E01.720p.proper-FlexGet'), \
            'Did not reject after proper timeframe'

    def test_no_propers(self, execute_task):
        """Series plugin: no propers at all"""
        task = execute_task('no_propers_1')
        assert len(task.accepted) == 1, 'broken badly'
        task = execute_task('no_propers_2')
        assert len(task.rejected) == 1, 'accepted proper'

    def test_min_max_propers(self, execute_task):
        """Series plugin: min max propers"""
        task = execute_task('min_max_quality_1')
        assert len(task.accepted) == 1, 'uhh, broken badly'
        task = execute_task('min_max_quality_2')
        assert len(task.accepted) == 1, 'should have accepted proper'

    def test_lot_propers(self, execute_task):
        """Series plugin: proper flood"""
        task = execute_task('lot_propers')
        assert len(task.accepted) == 1, 'should have accepted (only) one of the propers'

    def test_diff_quality_propers(self, execute_task):
        """Series plugin: proper in different/wrong quality"""
        task = execute_task('diff_quality_1')
        assert len(task.accepted) == 1
        task = execute_task('diff_quality_2')
        assert len(task.accepted) == 0, 'should not have accepted lower quality proper'

    def test_propers(self, execute_task):
        """Series plugin: proper accepted after episode is downloaded"""
        # start with normal download ...
        task = execute_task('propers_1')
        assert task.find_entry('accepted', title='Test.S01E01.720p-FlexGet'), \
            'Test.S01E01-FlexGet should have been accepted'

        # rejects downloaded
        task = execute_task('propers_1')
        assert task.find_entry('rejected', title='Test.S01E01.720p-FlexGet'), \
            'Test.S01E01-FlexGet should have been rejected'

        # accepts proper
        task = execute_task('propers_2')
        assert task.find_entry('accepted', title='Test.S01E01.720p.Proper-FlexGet'), \
            'new undownloaded proper should have been accepted'

        # reject downloaded proper
        task = execute_task('propers_2')
        assert task.find_entry('rejected', title='Test.S01E01.720p.Proper-FlexGet'), \
            'downloaded proper should have been rejected'

        # reject episode that has been downloaded normally and with proper
        task = execute_task('propers_3')
        assert task.find_entry('rejected', title='Test.S01E01.FlexGet'), \
            'Test.S01E01.FlexGet should have been rejected'

    def test_proper_available(self, execute_task):
        """Series plugin: proper available immediately"""
        task = execute_task('proper_at_first')
        assert task.find_entry('accepted', title='Foobar.S01E01.720p.proper.FlexGet'), \
            'Foobar.S01E01.720p.proper.FlexGet should have been accepted'

    def test_proper_upgrade(self, execute_task):
        """Series plugin: real proper after proper"""
        task = execute_task('proper_upgrade_1')
        assert task.find_entry('accepted', title='Test.S02E01.hdtv.proper')
        task = execute_task('proper_upgrade_2')
        assert task.find_entry('accepted', title='Test.S02E01.hdtv.real.proper')

    def test_anime_proper(self, execute_task):
        task = execute_task('anime_proper_1')
        assert task.accepted, 'ep should have accepted'
        task = execute_task('anime_proper_2')
        assert task.accepted, 'proper ep should have been accepted'

    def test_fastsub_proper(self, execute_task):
        task = execute_task('fastsub_proper_1')
        assert task.accepted, 'ep should have accepted'
        task = execute_task('fastsub_proper_2')
        assert task.accepted, 'proper ep should have been accepted'
        task = execute_task('fastsub_proper_3')
        assert task.accepted, 'proper ep should have been accepted'
        task = execute_task('fastsub_proper_4')
        assert task.accepted, 'proper ep should have been accepted'


class TestSimilarNames(object):
    # hmm, not very good way to test this .. seriesparser should be tested alone?

    config = """
        templates:
          global:
            parsing:
              series: {{parser}}
        tasks:
          test:
            mock:
              - {title: 'FooBar.S03E01.DSR-FlexGet'}
              - {title: 'FooBar: FirstAlt.S02E01.DSR-FlexGet'}
              - {title: 'FooBar: SecondAlt.S01E01.DSR-FlexGet'}
            series:
              - FooBar
              - 'FooBar: FirstAlt'
              - 'FooBar: SecondAlt'
          test_ambiguous:
            mock:
            - title: Foo.2.2
            series:
            - Foo:
                identified_by: sequence
            - Foo 2:
                identified_by: sequence
    """

    def test_names(self, execute_task):
        """Series plugin: similar namings"""
        task = execute_task('test')
        assert task.find_entry('accepted', title='FooBar.S03E01.DSR-FlexGet'), 'Standard failed?'
        assert task.find_entry('accepted', title='FooBar: FirstAlt.S02E01.DSR-FlexGet'), 'FirstAlt failed'
        assert task.find_entry('accepted', title='FooBar: SecondAlt.S01E01.DSR-FlexGet'), 'SecondAlt failed'

    def test_ambiguous(self, execute_task):
        task = execute_task('test_ambiguous')
        # In the event of ambiguous match, more specific one should be chosen
        assert task.find_entry('accepted', title='Foo.2.2')['series_name'] == 'Foo 2'


class TestDuplicates(object):
    config = """
        templates:
          global:
            parsing:
              series: {{parser}}
            # just cleans log a bit ..
            disable:
              - seen

        tasks:
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

    def test_dupes(self, execute_task):
        """Series plugin: dupes with same quality"""
        task = execute_task('test_dupes')
        assert len(task.accepted) == 1, 'accepted both'

    def test_true_dupes(self, execute_task):
        """Series plugin: true duplicate items"""
        task = execute_task('test_true_dupes')
        assert len(task.accepted) == 1, 'should have accepted (only) one'

    def test_downloaded(self, execute_task):
        """Series plugin: multiple downloaded and new episodes are handled correctly"""

        task = execute_task('test_1')
        task = execute_task('test_2')

        # these should be accepted
        accepted = ['Foo.Bar.S02E03.HDTV.XviD-FlexGet', 'Foo.Bar.S02E05.720p.HDTV.XviD-YYY']
        for item in accepted:
            assert task.find_entry('accepted', title=item), \
                '%s should have been accepted' % item

        # these should be rejected
        rejected = ['Foo.Bar.S02E04.XviD-2HD[ASDF]', 'Foo.Bar.S02E04.HDTV.720p.XviD-2HD[FlexGet]',
                    'Foo.Bar.S02E04.DSRIP.XviD-2HD[ASDF]', 'Foo.Bar.S02E04.HDTV.1080p.XviD-2HD[ASDF]']
        for item in rejected:
            assert task.find_entry('rejected', title=item), \
                '%s should have been rejected' % item


class TestQualities(object):
    config = """
        templates:
          global:
            parsing:
              series: {{parser}}
            disable: builtins
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
              - FooBum:
                  quality: 720p-1080i
                  upgrade: yes
              - FooD:
                  target: 720p
                  timeframe: 0 hours
                  upgrade: yes
        tasks:
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
          quality_upgrade_1:
            mock:
              - title: FooBum.S03E01.1080p # too high
              - title: FooBum.S03E01.hdtv # too low
              - title: FooBum.S03E01.720p # in range
          quality_upgrade_2:
            mock:
              - title: FooBum.S03E01.1080i # should be upgraded to
              - title: FooBum.S03E01.720p-ver2 # Duplicate ep
          target_1:
            mock:
              - title: Food.S06E11.sdtv
              - title: Food.S06E11.hdtv
          target_2:
            mock:
              - title: Food.S06E11.1080p
              - title: Food.S06E11.720p
    """

    def test_qualities(self, execute_task):
        """Series plugin: qualities"""
        task = execute_task('test_1')

        assert task.find_entry('accepted', title='FooBar.S01E01.PDTV-FlexGet'), \
            'Didn''t accept FooBar.S01E01.PDTV-FlexGet'
        assert task.find_entry('accepted', title='FooBar.S01E01.1080p-FlexGet'), \
            'Didn''t accept FooBar.S01E01.1080p-FlexGet'

        assert not task.find_entry('accepted', title='FooBar.S01E01.HR-FlexGet'), \
            'Accepted FooBar.S01E01.HR-FlexGet'

        task = execute_task('test_2')

        assert task.find_entry('accepted', title='FooBar.S01E01.720p-FlexGet'), \
            'Didn''t accept FooBar.S01E01.720p-FlexGet'

        # test that it rejects them afterwards

        task = execute_task('test_1')

        assert task.find_entry('rejected', title='FooBar.S01E01.PDTV-FlexGet'), \
            'Didn\'t reject FooBar.S01E01.PDTV-FlexGet'
        assert task.find_entry('rejected', title='FooBar.S01E01.1080p-FlexGet'), \
            'Didn\'t reject FooBar.S01E01.1080p-FlexGet'

        assert not task.find_entry('accepted', title='FooBar.S01E01.HR-FlexGet'), \
            'Accepted FooBar.S01E01.HR-FlexGet'

    def test_propers(self, execute_task):
        """Series plugin: qualities + propers"""
        task = execute_task('propers_1')
        assert task.accepted
        task = execute_task('propers_2')
        assert task.accepted, 'proper not accepted'
        task = execute_task('propers_2')
        assert not task.accepted, 'proper accepted again'

    def test_qualities_upgrade(self, execute_task):
        task = execute_task('upgrade_1')
        assert task.find_entry('accepted', title='FooBaz.S01E02.HR-FlexGet'), 'HR quality should be accepted'
        assert len(task.accepted) == 1, 'Only best quality should be accepted'
        task = execute_task('upgrade_2')
        assert task.find_entry('accepted', title='FooBaz.S01E02.720p-FlexGet'), '720p quality should be accepted'
        assert len(task.accepted) == 1, 'Only best quality should be accepted'
        task = execute_task('upgrade_3')
        assert not task.accepted, 'Should not have accepted worse qualities'

    def test_quality_upgrade(self, execute_task):
        task = execute_task('quality_upgrade_1')
        assert len(task.accepted) == 1, 'Only one ep should have passed quality filter'
        assert task.find_entry('accepted', title='FooBum.S03E01.720p')
        task = execute_task('quality_upgrade_2')
        assert len(task.accepted) == 1, 'one ep should be valid upgrade'
        assert task.find_entry('accepted', title='FooBum.S03E01.1080i')

    def test_target_upgrade(self, execute_task):
        task = execute_task('target_1')
        assert len(task.accepted) == 1, 'Only one ep should have been grabbed'
        assert task.find_entry('accepted', title='Food.S06E11.hdtv')
        task = execute_task('target_2')
        assert len(task.accepted) == 1, 'one ep should be valid upgrade'
        assert task.find_entry('accepted', title='Food.S06E11.720p'), 'Should upgrade to `target`'


class TestIdioticNumbering(object):
    config = """
        templates:
          global:
            parsing:
              series: {{parser}}
            series:
              - FooBar:
                  identified_by: ep

        tasks:
          test_1:
            mock:
              - {title: 'FooBar.S01E01.PDTV-FlexGet'}
          test_2:
            mock:
              - {title: 'FooBar.102.PDTV-FlexGet'}
    """

    def test_idiotic(self, execute_task):
        """Series plugin: idiotic numbering scheme"""

        task = execute_task('test_1')
        task = execute_task('test_2')
        entry = task.find_entry(title='FooBar.102.PDTV-FlexGet')
        assert entry, 'entry not found?'
        assert entry['series_season'] == 1, 'season not detected'
        assert entry['series_episode'] == 2, 'episode not detected'


class TestNormalization(object):
    config = """
        templates:
          global:
            parsing:
              series: {{parser}}
            disable: [seen]
        tasks:
          test_1:
            mock:
              - {title: 'FooBar.S01E01.PDTV-FlexGet'}
            series:
              - FOOBAR
          test_2:
            mock:
              - {title: 'FooBar.S01E01.PDTV-aoeu'}
            series:
              - foobar
          test_3:
            mock:
              - title: Foo bar & co 2012.s01e01.sdtv.a
            series:
              - foo bar & co 2012
          test_4:
            mock:
              - title: Foo bar & co 2012.s01e01.sdtv.b
            series:
              - Foo/Bar and Co. (2012)
    """

    def test_capitalization(self, execute_task):
        """Series plugin: configuration capitalization"""
        task = execute_task('test_1')
        assert task.find_entry('accepted', title='FooBar.S01E01.PDTV-FlexGet')
        task = execute_task('test_2')
        assert task.find_entry('rejected', title='FooBar.S01E01.PDTV-aoeu')

    def test_normalization(self, execute_task):
        task = execute_task('test_3')
        assert task.find_entry('accepted', title='Foo bar & co 2012.s01e01.sdtv.a')
        task = execute_task('test_4')
        assert task.find_entry('rejected', title='Foo bar & co 2012.s01e01.sdtv.b')


class TestMixedNumbering(object):
    config = """
        templates:
          global:
            parsing:
              series: {{parser}}
            series:
              - FooBar:
                  identified_by: ep

        tasks:
          test_1:
            mock:
              - {title: 'FooBar.S03E07.PDTV-FlexGet'}
          test_2:
            mock:
              - {title: 'FooBar.0307.PDTV-FlexGet'}
    """

    def test_mixednumbering(self, execute_task):
        """Series plugin: Mixed series numbering"""

        task = execute_task('test_1')
        assert task.find_entry('accepted', title='FooBar.S03E07.PDTV-FlexGet')
        task = execute_task('test_2')
        assert task.find_entry('rejected', title='FooBar.0307.PDTV-FlexGet')


class TestExact(object):
    config = """
        templates:
          global:
            parsing:
              series: {{parser}}
        tasks:
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

    def test_auto(self, execute_task):
        """Series plugin: auto enable exact"""
        task = execute_task('auto')
        assert task.find_entry('accepted', title='ABC.S01E01.PDTV-FlexGet')
        assert task.find_entry('accepted', title='ABC.LA.S01E01.PDTV-FlexGet')
        assert task.find_entry('accepted', title='ABC.MIAMI.S01E01.PDTV-FlexGet')

    def test_with_name_regexp(self, execute_task):
        task = execute_task('name_regexp')
        assert task.find_entry('accepted', title='show s09e05 hdtv')
        assert not task.find_entry('accepted', title='show a s09e06 hdtv')

    def test_dated_show(self, execute_task):
        task = execute_task('date')
        assert task.find_entry('accepted', title='date show 04.01.2011 hdtv')
        assert not task.find_entry('accepted', title='date show b 04.02.2011 hdtv')


class TestTimeframe(object):
    config = """
        templates:
          global:
            parsing:
              series: {{parser}}
            series:
              - test:
                  timeframe: 5 hours
                  target: 720p
        tasks:
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
                  target: 720p
                  quality: hdtv+ <=720p
            mock:
              - {title: 'MM Test.S01E02.pdtv-FlexGet'}
              - {title: 'MM Test.S01E02.1080p-FlexGet'}

          test_min_max_pass:
            series:
              - mm test:
                  timeframe: 5 hours
                  target: 720p
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

          test_with_quality_1:
            series:
            - q test:
                timeframe: 5 hours
                quality: hdtv+
                target: 720p
            mock:
            - title: q test s01e01 pdtv 720p

          test_with_quality_2:
            series:
            - q test:
                timeframe: 5 hours
                quality: hdtv+
                target: 720p
            mock:
            - title: q test s01e01 hdtv

    """

    def test_no_waiting(self, execute_task):
        """Series plugin: no timeframe waiting needed"""
        task = execute_task('test_no_waiting')
        assert task.find_entry('accepted', title='Test.S01E01.720p-FlexGet'), \
            '720p not accepted immediattely'

    def test_stop_waiting(self, execute_task):
        """Series plugin: timeframe quality appears, stop waiting, proper appears"""
        task = execute_task('test_stop_waiting_1')
        assert task.entries and not task.accepted
        task = execute_task('test_stop_waiting_2')
        assert task.find_entry('accepted', title='Test.S01E02.720p-FlexGet'), \
            '720p should have caused stop waiting'
        task = execute_task('test_proper_afterwards')
        assert task.find_entry('accepted', title='Test.S01E02.720p.Proper-FlexGet'), \
            'proper should have been accepted'

    def test_expires(self, execute_task):
        """Series plugin: timeframe expires"""
        # first execution should not accept anything
        task = execute_task('test_expires')
        assert not task.accepted

        # let 3 hours pass
        age_series(hours=3)
        task = execute_task('test_expires')
        assert not task.accepted, 'expired too soon'

        # let another 3 hours pass, should expire now!
        age_series(hours=6)
        task = execute_task('test_expires')
        assert task.accepted, 'timeframe didn\'t expire'

    def test_min_max_fail(self, execute_task):
        task = execute_task('test_min_max_fail')
        assert not task.accepted

        # Let 6 hours pass, timeframe should not even been started, as pdtv doesn't meet min_quality
        age_series(hours=6)
        task = execute_task('test_min_max_fail')
        assert task.entries and not task.accepted

    def test_min_max_pass(self, execute_task):
        task = execute_task('test_min_max_pass')
        assert not task.accepted

        # Let 6 hours pass, timeframe should expire and accept hdtv copy
        age_series(hours=6)
        task = execute_task('test_min_max_pass')
        assert task.find_entry('accepted', title='MM Test.S01E02.hdtv-FlexGet')
        assert len(task.accepted) == 1

    def test_qualities_fail(self, execute_task):
        task = execute_task('test_qualities_fail')
        assert task.find_entry('accepted', title='Q Test.S01E02.1080p-FlexGet'), \
            'should have accepted wanted quality'
        assert len(task.accepted) == 1

        # Let 6 hours pass, timeframe should not even been started, as we already have one of our qualities
        age_series(hours=6)
        task = execute_task('test_qualities_fail')
        assert task.entries and not task.accepted

    def test_qualities_pass(self, execute_task):
        task = execute_task('test_qualities_pass')
        assert not task.accepted, 'None of the qualities should have matched'

        # Let 6 hours pass, timeframe should expire and accept 1080p copy
        age_series(hours=6)
        task = execute_task('test_qualities_pass')
        assert task.find_entry('accepted', title='Q Test.S01E02.1080p-FlexGet')
        assert len(task.accepted) == 1

    def test_with_quality(self, execute_task):
        task = execute_task('test_with_quality_1')
        assert not task.accepted, 'Entry does not pass quality'

        age_series(hours=6)
        # Entry from first test feed should not pass quality
        task = execute_task('test_with_quality_1')
        assert not task.accepted, 'Entry does not pass quality'
        # Timeframe should not yet have started
        task = execute_task('test_with_quality_2')
        assert not task.accepted, 'Timeframe should not yet have passed'

        age_series(hours=6)
        task = execute_task('test_with_quality_2')
        assert task.accepted, 'Timeframe should have passed'


class TestBacklog(object):
    config = """
        templates:
          global:
            parsing:
              series: {{parser}}
        tasks:
          backlog:
            mock:
              - {title: 'Test.S01E01.hdtv-FlexGet'}
            series:
              - test: {timeframe: 6 hours}
    """

    def testBacklog(self, manager, execute_task):
        """Series plugin: backlog"""
        task = execute_task('backlog')
        assert task.entries and not task.accepted, 'no entries at the start'
        # simulate test going away from the task
        del (manager.config['tasks']['backlog']['mock'])
        age_series(hours=12)
        task = execute_task('backlog')
        assert task.accepted, 'backlog is not injecting episodes'


class TestManipulate(object):
    """Tests that it's possible to manipulate entries before they're parsed by series plugin"""

    config = """
        templates:
          global:
            parsing:
              series: {{parser}}
        tasks:
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

    def testManipulate(self, execute_task):
        """Series plugin: test manipulation priority"""
        # should not work with the prefix
        task = execute_task('test_1')
        assert not task.accepted, 'series accepted even with prefix?'
        assert not task.accepted, 'series rejecte even with prefix?'
        task = execute_task('test_2')
        assert task.accepted, 'manipulate failed to pre-clean title'


class TestFromGroup(object):
    config = """
        templates:
          global:
            parsing:
              series: {{parser}}
        tasks:
          test:
            mock:
              - {title: '[Ignored] Test 12'}
              - {title: '[FlexGet] Test 12'}
              - {title: 'Test.13.HDTV-Ignored'}
              - {title: 'Test.13.HDTV-FlexGet'}
              - {title: 'Test.14.HDTV-Name'}
              - {title: 'Test :: h264 10-bit | Softsubs (FlexGet) | Episode 3'}
              - {title: 'Test :: h264 10-bit | Softsubs (Ignore) | Episode 3'}
            series:
              - test: {from_group: [Name, FlexGet]}
    """

    def testFromGroup(self, execute_task):
        """Series plugin: test from_group"""
        task = execute_task('test')
        assert task.find_entry('accepted', title='[FlexGet] Test 12')
        assert task.find_entry('accepted', title='Test.13.HDTV-FlexGet')
        assert task.find_entry('accepted', title='Test.14.HDTV-Name')
        assert task.find_entry('accepted', title='Test :: h264 10-bit | Softsubs (FlexGet) | Episode 3')


class TestBegin(object):
    config = """
        templates:
          global:
            parsing:
              series: {{parser}}
          eps:
            mock:
              - {title: 'WTest.S02E03.HDTV.XViD-FlexGet'}
              - {title: 'W2Test.S02E03.HDTV.XViD-FlexGet'}
        tasks:
          before_ep_test:
            template: eps
            series:
              - WTest:
                  begin: S02E05
              - W2Test:
                  begin: S03E02
          after_ep_test:
            template: eps
            series:
              - WTest:
                  begin: S02E03
              - W2Test:
                  begin: S02E01
          before_seq_test:
            mock:
            - title: WTest.1.HDTV.XViD-FlexGet
            - title: W2Test.13.HDTV.XViD-FlexGet
            series:
              - WTest:
                  begin: 2
              - W2Test:
                  begin: 120
          after_seq_test:
            mock:
            - title: WTest.2.HDTV.XViD-FlexGet
            - title: W2Test.123.HDTV.XViD-FlexGet
            series:
              - WTest:
                  begin: 2
              - W2Test:
                  begin: 120
          before_date_test:
            mock:
            - title: WTest.2001.6.6.HDTV.XViD-FlexGet
            - title: W2Test.12.30.2012.HDTV.XViD-FlexGet
            series:
              - WTest:
                  begin: '2009-05-05'
              - W2Test:
                  begin: '2012-12-31'
          after_date_test:
            mock:
            - title: WTest.2009.5.5.HDTV.XViD-FlexGet
            - title: W2Test.1.1.2013.HDTV.XViD-FlexGet
            series:
              - WTest:
                  begin: '2009-05-05'
              - W2Test:
                  begin: '2012-12-31'
          test_advancement1:
            mock:
            - title: WTest.S01E01
            series:
            - WTest
          test_advancement2:
            mock:
            - title: WTest.S03E01
            series:
            - WTest
          test_advancement3:
            mock:
            - title: WTest.S03E01
            series:
            - WTest:
                begin: S03E01

    """

    def test_before_ep(self, execute_task):
        task = execute_task('before_ep_test')
        assert not task.accepted, 'No entries should have been accepted, they are before the begin episode'

    def test_after_ep(self, execute_task):
        task = execute_task('after_ep_test')
        assert len(task.accepted) == 2, 'Entries should have been accepted, they are not before the begin episode'

    def test_before_seq(self, execute_task):
        task = execute_task('before_seq_test')
        assert not task.accepted, 'No entries should have been accepted, they are before the begin episode'

    def test_after_seq(self, execute_task):
        task = execute_task('after_seq_test')
        assert len(task.accepted) == 2, 'Entries should have been accepted, they are not before the begin episode'

    def test_before_date(self, execute_task):
        task = execute_task('before_date_test')
        assert not task.accepted, 'No entries should have been accepted, they are before the begin episode'

    def test_after_date(self, execute_task):
        task = execute_task('after_date_test')
        assert len(task.accepted) == 2, 'Entries should have been accepted, they are not before the begin episode'

    def test_advancement(self, execute_task):
        # Put S01E01 into the database as latest download
        task = execute_task('test_advancement1')
        assert task.accepted
        # Just verify regular ep advancement would block S03E01
        task = execute_task('test_advancement2')
        assert not task.accepted, 'Episode advancement should have blocked'
        # Make sure ep advancement doesn't block it when we've set begin to that ep
        task = execute_task('test_advancement3')
        assert task.accepted, 'Episode should have been accepted'


class TestSeriesPremiere(object):
    config = """
        templates:
          global:
            parsing:
              series: {{parser}}
            metainfo_series: yes
            series_premiere: yes
        tasks:
          test:
            mock:
              - {title: 'Foobar.S01E01.PDTV-FlexGet'}
              - {title: 'Foobar.S01E11.1080p-FlexGet'}
              - {title: 'Foobar.S02E02.HR-FlexGet'}
    """

    def testOnlyPremieres(self, execute_task):
        """Test series premiere"""
        task = execute_task('test')
        assert task.find_entry('accepted', title='Foobar.S01E01.PDTV-FlexGet',
                               series_name='Foobar', series_season=1,
                               series_episode=1), 'Series premiere should have been accepted'
        assert len(task.accepted) == 1
        # TODO: Add more tests, test interaction with series plugin and series_exists


class TestImportSeries(object):
    config = """
        templates:
          global:
            parsing:
              series: {{parser}}
        tasks:
          timeframe_max:
            configure_series:
              settings:
                propers: 12 hours
                target: 720p
                timeframe: 5 minutes
                quality: "<=720p <=bluray"
              from:
                mock:
                  - title: the show
            mock:
              - title: the show s03e02 1080p bluray
              - title: the show s03e02 hdtv
          test_import_altnames:
            configure_series:
              from:
                mock:
                  - {title: 'the show', configure_series_alternate_name: 'le show'}
            mock:
              - title: le show s03e03
    """

    def test_timeframe_max(self, execute_task):
        """Tests configure_series as well as timeframe with max_quality."""
        task = execute_task('timeframe_max')
        assert not task.accepted, 'Entry shouldnot have been accepted on first run.'
        age_series(minutes=6)
        task = execute_task('timeframe_max')
        assert task.find_entry('accepted', title='the show s03e02 hdtv'), \
            'hdtv should have been accepted after timeframe.'

    def test_import_altnames(self, execute_task):
        """Tests configure_series with alternate_name."""
        task = execute_task('test_import_altnames')
        entry = task.find_entry(title='le show s03e03')
        assert entry.accepted, 'entry matching series alternate name should have been accepted.'
        assert entry['series_name'] == 'the show', 'entry series should be set to the main name'


class TestIDTypes(object):
    config = """
        templates:
          global:
            parsing:
              series: {{parser}}
        tasks:
          all_types:
            series:
              - episode
              - seasonless episode
              - date
              - sequence
              - stupid id:
                  id_regexp: (\\dcat)
            mock:
              - title: episode S03E04
              - title: episode 3x05
              - title: date 2011.4.3 other crap hdtv
              - title: date 4.5.11
              - title: sequence 003
              - title: sequence 4
              - title: stupid id 3cat
              - title: seasonless episode e01
    """

    def test_id_types(self, execute_task):
        task = execute_task('all_types')
        for entry in task.entries:
            assert entry['series_name'], '%s not parsed by series plugin' % entry['title']
            assert entry['series_id_type'] in entry['series_name']


class TestCaseChange(object):
    config = """
        templates:
          global:
            parsing:
              series: {{parser}}
        tasks:
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

    def test_case_change(self, execute_task):
        task = execute_task('first')
        # Make sure series_name uses case from config, make sure episode is accepted
        assert task.find_entry('accepted', title='theshow s02e04', series_name='TheShow')
        task = execute_task('second')
        # Make sure series_name uses new case from config, make sure ep is rejected because we have a copy
        assert task.find_entry('rejected', title='thEshoW s02e04 other', series_name='THESHOW')


class TestInvalidSeries(object):
    config = """
        templates:
          global:
            parsing:
              series: {{parser}}
        tasks:
          blank:
            mock:
              - title: whatever
            series:
              - '':
                  quality: 720p
    """

    def test_blank_series(self, execute_task):
        """Make sure a blank series doesn't crash."""
        task = execute_task('blank')
        assert not task.aborted, 'Task should not have aborted'


class TestDoubleEps(object):
    config = """
        templates:
          global:
            parsing:
              series: {{parser}}
        tasks:
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

    def test_double(self, execute_task):
        # First should be accepted
        task = execute_task('test_double1')
        assert task.find_entry('accepted', title='double S01E02-E03')

        # We already got ep 3 as part of double, should not be accepted
        task = execute_task('test_double2')
        assert not task.find_entry('accepted', title='double S01E03')

    def test_double_prefered(self, execute_task):
        # Given a choice of single or double ep at same quality, grab the double
        task = execute_task('test_double_prefered')
        assert task.find_entry('accepted', title='double S02E03-04')
        assert not task.find_entry('accepted', title='S02E03')


class TestAutoLockin(object):
    config = """
        templates:
          global:
            parsing:
              series: {{parser}}
            series:
            - FooBar
            - BarFood
        tasks:
          try_date_1:
            mock:
            - title: FooBar 2012-10-10 HDTV
          lock_ep:
            mock:
            - title: FooBar S01E01 HDTV
            - title: FooBar S01E02 HDTV
            - title: FooBar S01E03 HDTV
          try_date_2:
            mock:
            - title: FooBar 2012-10-11 HDTV
          test_special_lock:
            mock:
            - title: BarFood christmas special HDTV
            - title: BarFood easter special HDTV
            - title: BarFood haloween special HDTV
            - title: BarFood bad special HDTV
          try_reg:
            mock:
            - title: BarFood S01E01 HDTV
            - title: BarFood 2012-9-9 HDTV

    """

    def test_ep_lockin(self, execute_task):
        task = execute_task('try_date_1')
        assert task.find_entry('accepted', title='FooBar 2012-10-10 HDTV'), \
            'dates should be accepted before locked in on an identifier type'
        task = execute_task('lock_ep')
        assert len(task.accepted) == 3, 'All ep mode episodes should have been accepted'
        task = execute_task('try_date_2')
        assert not task.find_entry('accepted', title='FooBar 2012-10-11 HDTV'), \
            'dates should not be accepted after series has locked in to ep mode'

    def test_special_lock(self, execute_task):
        """Make sure series plugin does not lock in to type 'special'"""
        task = execute_task('test_special_lock')
        assert len(task.accepted) == 4, 'All specials should have been accepted'
        task = execute_task('try_reg')
        assert len(task.accepted) == 2, 'Specials should not have caused episode type lock-in'


class TestReruns(object):
    config = """
        templates:
          global:
            parsing:
              series: {{parser}}
        tasks:
          one_accept:
            mock:
            - title: the show s01e01
            - title: the show s01e01 different
            series:
            - the show
            rerun: 2
            mock_output: yes
    """

    def test_one_accept(self, execute_task):
        task = execute_task('one_accept')
        assert len(task.mock_output) == 1, \
            'should have accepted once!: %s' % ', '.join(e['title'] for e in task.mock_output)


class TestSpecials(object):
    config = """
        templates:
          global:
            parsing:
              series: {{parser}}
        tasks:
          preferspecials:
            mock:
            - title: the show s03e04 special
            series:
            - the show:
                prefer_specials: True

          nopreferspecials:
            mock:
            - title: the show s03e05 special
            series:
            - the show:
                prefer_specials: False

          assumespecial:
            mock:
            - title: the show SOMETHING
            series:
            - the show:
                assume_special: True

          noassumespecial:
            mock:
            - title: the show SOMETHING
            series:
            - the show:
                assume_special: False
    """

    def test_prefer_specials(self, execute_task):
        # Test that an entry matching both ep and special is flagged as a special when prefer_specials is True
        task = execute_task('preferspecials')
        entry = task.find_entry('accepted', title='the show s03e04 special')
        assert entry.get('series_id_type') == 'special', 'Entry which should have been flagged a special was not.'

    def test_not_prefer_specials(self, execute_task):
        # Test that an entry matching both ep and special is flagged as an ep when prefer_specials is False
        task = execute_task('nopreferspecials')
        entry = task.find_entry('accepted', title='the show s03e05 special')
        assert entry.get('series_id_type') != 'special', 'Entry which should not have been flagged a special was.'

    def test_assume_special(self, execute_task):
        # Test that an entry with no ID found gets flagged as a special and accepted if assume_special is True
        task = execute_task('assumespecial')
        entry = task.find_entry(title='the show SOMETHING')
        assert entry.get('series_id_type') == 'special', 'Entry which should have been flagged as a special was not.'
        assert entry.accepted, 'Entry which should have been accepted was not.'

    def test_not_assume_special(self, execute_task):
        # Test that an entry with no ID found does not get flagged as a special and accepted if assume_special is False
        task = execute_task('noassumespecial')
        entry = task.find_entry(title='the show SOMETHING')
        assert entry.get('series_id_type') != 'special', 'Entry which should not have been flagged as a special was.'
        assert not entry.accepted, 'Entry which should not have been accepted was.'


class TestAlternateNames(object):
    config = """
        templates:
          global:
            parsing:
              series: {{parser}}
        tasks:
          alternate_name:
            series:
              - Some Show:
                  begin: S01E01
                  alternate_name: Other Show
          another_alternate_name:
            series:
              - Some Show:
                  alternate_name: Good Show
          set_other_alternate_name:
            mock:
              - title: Third.Show.S01E01
              - title: Other.Show.S01E01
            series:
              - Some Show:
                  alternate_name: Third Show
            rerun: 0
          duplicate_names_in_different_series:
            series:
              - First Show:
                 begin: S01E01
                 alternate_name: Third Show
              - Second Show:
                 begin: S01E01
                 alternate_name: Third Show
    """

    def test_set_alternate_name(self, execute_task):
        # Tests that old alternate names are not kept in the database.
        task = execute_task('alternate_name')
        task = execute_task('set_other_alternate_name')
        assert task.find_entry('accepted', title='Third.Show.S01E01'), \
            'A new alternate name should have been associated with the series.'
        assert task.find_entry('undecided', title='Other.Show.S01E01'), \
            'The old alternate name for the series is still present.'

    def test_duplicate_alternate_names_in_different_series(self, execute_task):
        with pytest.raises(TaskAbort) as ex:
            execute_task('duplicate_names_in_different_series')
        # only test that the reason is about alternate names, not which names.
        reason = 'Error adding alternate name'
        assert ex.value.reason[:27] == reason, \
            'Wrong reason for task abortion. Should be about duplicate alternate names.'

    # Test the DB behaves like we expect ie. alternate names cannot
    def test_alternate_names_are_removed_from_db(self, execute_task):
        from flexget.manager import Session
        from flexget.plugins.filter.series import AlternateNames
        with Session() as session:
            execute_task('alternate_name')
            # test the current state of alternate names
            assert len(session.query(AlternateNames).all()) == 1, 'There should be one alternate name present.'
            assert session.query(AlternateNames).first().alt_name == 'Other Show', \
                'Alternate name should have been Other Show.'

            # run another task that overwrites the alternate names
            execute_task('another_alternate_name')
            assert len(session.query(AlternateNames).all()) == 1, \
                'The old alternate name should have been removed from the database.'
            assert session.query(AlternateNames).first().alt_name == 'Good Show', \
                'The alternate name in the database should be the new one, Good Show.'


class TestCLI(object):
    config = """
        templates:
          global:
            parsing:
              series: {{parser}}
        tasks:
          learn_series:
            series:
            - Some Show
            - Other Show
            mock:
            - title: Some Series S01E01
            - title: Other Series S01E02
    """

    def test_series_list(self, manager, execute_task):
        """Very rudimentary test, mostly makes sure this doesn't crash."""
        execute_task('learn_series')
        options = get_parser().parse_args(['series', 'list', '--porcelain'])
        buffer = StringIO()
        with capture_output(buffer, loglevel='error'):
            manager.handle_cli(options=options)
        lines = buffer.getvalue().split('\n')
        assert all(any(line.lstrip().startswith(series) for line in lines) for series in ['Some Show', 'Other Show'])


class TestSeriesRemove(object):
    config = """
        templates:
          global:
            parsing:
              series: {{parser}}
        tasks:
          get_episode:
            seen: local
            series:
            - My Show
            mock:
            - title: My Show S01E01 1080p
            - title: My Show S01E01 720p
          remove_episode:
            seen: no
            mock:
            - title: My Show S01E01
              series_name: My Show
              series_id: S01E01
            accept_all: yes
            series_remove: yes
    """

    def test_remove_episode(self, execute_task):
        task = execute_task('get_episode')
        assert len(task.accepted) == 1
        first_rls = task.accepted[0]
        task = execute_task('get_episode')
        assert not task.accepted, 'series plugin duplicate blocking not working?'
        task = execute_task('remove_episode')
        task = execute_task('get_episode')
        assert len(task.accepted) == 1, 'new release not accepted after forgetting ep'
        assert task.accepted[0] != first_rls, 'same release accepted on second run'


class TestSeriesSeasonPack(object):
    _config = """
      templates:
        global:
          parsing:
            series: internal
          series:
          - foo:
              season_packs: yes
          - bar:
              season_packs: yes
              tracking: backfill
          - baz:
              season_packs: 3
          - boo:
              season_packs: always
          - bla:
              season_packs: only
          - bro:
              season_packs:
                threshold: 1
                reject_eps: yes
      tasks:
        multiple_formats:
          mock:
          - title: foo.s01.720p-flexget
          - title: foo.2xALL.720p-flexget
        foo_s01:
          mock:
          - title: foo.s01.720p-flexget
        foo_s02:
          mock:
          - title: foo.s02.720p-flexget
        foo_s03:
          mock:
          - title: foo.s03.720p-flexget
        foo_s01ep1:
          mock:
          - title: foo.s01e1.720p-flexget
        foo_s02ep1:
          mock:
          - title: foo.s02e1.720p-flexget
        season_pack_priority:
          mock:
          - title: foo.s01e1.720p-flexget
          - title: foo.s01e2.720p-flexget
          - title: foo.s01e3.720p-flexget
          - title: foo.s01e4.720p-flexget
          - title: foo.s01e5.720p-flexget
          - title: foo.s01.720p-flexget
        respect_begin:
          series:
          - bar:
              begin: s02e01
              season_packs: yes
          mock:
          - title: bar.s01.720p-flexget
          - title: bar.s02.720p-flexget
        several_seasons:
          mock:
          - title: foo.s03.720p-flexget
          - title: foo.s07.720p-flexget
          - title: foo.s03.1080p-flexget
          - title: foo.s06.720p-flexget
          - title: foo.s09.720p-flexget
        test_backfill_1:
          mock:
          - title: bar.s03.720p-flexget
        test_backfill_2:
          mock:
          - title: bar.s02.720p-flexget
        test_backfill_3:
          mock:
          - title: bar.s03e01.720p-flexget
        test_backfill_4:
          mock:
          - title: bar.s02e01.1080p-flexget
        test_specific_season_pack_threshold_1:
          mock:
          - title: baz.s01e01.720p-flexget
          - title: baz.s01e02.720p-flexget
          - title: baz.s01e03.720p-flexget
        test_specific_season_pack_threshold_2:
          mock:
          - title: baz.s01.720p-flexget
        test_specific_season_pack_threshold_3:
          mock:
          - title: baz.s01e01.720p-flexget
          - title: baz.s01e02.720p-flexget
          - title: baz.s01e03.720p-flexget
          - title: baz.s01e04.720p-flexget
        test_always_get_season_pack_1:
          mock:
          - title: boo.s01e01.720p-flexget
          - title: boo.s01e02.720p-flexget
          - title: boo.s01e03.720p-flexget
          - title: boo.s01e04.720p-flexget
        test_always_get_season_pack_2:
          mock:
          - title: boo.s01.720p-flexget
        test_only_get_season_packs:
          mock:
          - title: bla.s01.720p-flexget
          - title: bla.s02e01.720p-flexget
        test_proper_season_pack:
          mock:
          - title: foo.s01.720p-flexget
          - title: foo.s01.720p.proper-flexget
        test_proper_season_pack_2:
          mock:
          - title: foo.s01.720p-flexget
        test_proper_season_pack_3:
          mock:
          - title: foo.s01.720p.proper-flexget
        test_all_series:
          mock:
          - title: show.name.s01.720p.HDTV-Group
          all_series:
            season_packs: yes
        test_with_dict_config_1:
          mock:
          - title: bro.s01e01.720p.HDTV-Flexget
          - title: bro.s01.720p.HDTV-Flexget
        test_with_dict_config_2:
          mock:
          - title: bro.s02.720p.HDTV-Flexget
          
    """

    @pytest.fixture()
    def config(self):
        """Overrides outer config fixture since season pack support does not work with guessit parser"""
        return self._config

    def test_season_pack_simple(self, execute_task):
        task = execute_task('foo_s01')
        assert len(task.accepted) == 1

    def test_basic_tracking(self, execute_task):
        task = execute_task('foo_s01')
        assert len(task.accepted) == 1

        task = execute_task('foo_s01ep1')
        assert len(task.accepted) == 0

        task = execute_task('foo_s02ep1')
        assert len(task.accepted) == 1

    def test_season_pack_takes_priority(self, execute_task):
        task = execute_task('season_pack_priority')
        assert len(task.accepted) == 1
        entry = task.find_entry(title='foo.s01.720p-flexget')
        assert entry.accepted

    def test_respect_begin(self, execute_task):
        task = execute_task('respect_begin')
        assert len(task.accepted) == 1
        entry = task.find_entry(title='bar.s02.720p-flexget')
        assert entry.accepted

    def test_tracking_rules_old_eps(self, execute_task):
        task = execute_task('foo_s01')
        assert len(task.accepted) == 1

        task = execute_task('foo_s02')
        assert len(task.accepted) == 1

        task = execute_task('foo_s01ep1')
        assert not task.accepted

    def test_tracking_rules_old_season(self, execute_task):
        task = execute_task('foo_s02')
        assert len(task.accepted) == 1

        task = execute_task('foo_s01')
        assert not task.accepted

    def test_tracking_rules_new_season(self, execute_task):
        task = execute_task('foo_s01')
        assert len(task.accepted) == 1

        task = execute_task('foo_s03')
        assert not task.accepted

    def test_several_seasons(self, execute_task):
        task = execute_task('several_seasons')
        assert len(task.accepted) == 4

    def test_multiple_formats(self, execute_task):
        task = execute_task('multiple_formats')
        assert len(task.accepted) == 2

    def test_backfill(self, execute_task):
        task = execute_task('test_backfill_1')
        assert len(task.accepted) == 1

        task = execute_task('test_backfill_2')
        assert len(task.accepted) == 1

        task = execute_task('test_backfill_3')
        assert not task.accepted

        task = execute_task('test_backfill_4')
        assert not task.accepted

    def test_default_threshold(self, execute_task):
        task = execute_task('foo_s01ep1')
        assert len(task.accepted) == 1

        task = execute_task('foo_s01')
        assert len(task.accepted) == 0

    def test_specific_season_pack_threshold_positive(self, execute_task):
        task = execute_task('test_specific_season_pack_threshold_1')
        assert len(task.accepted) == 3

        task = execute_task('test_specific_season_pack_threshold_2')
        assert len(task.accepted) == 1

    def test_specific_season_pack_threshold_negative(self, execute_task):
        task = execute_task('test_specific_season_pack_threshold_3')
        assert len(task.accepted) == 4

        task = execute_task('test_specific_season_pack_threshold_2')
        assert not task.accepted

    def test_loose_threshold(self, execute_task):
        task = execute_task('test_always_get_season_pack_1')
        assert len(task.accepted) == 4

        task = execute_task('test_always_get_season_pack_2')
        assert len(task.accepted) == 1

    def test_exclusive(self, execute_task):
        task = execute_task('test_only_get_season_packs')
        assert len(task.accepted) == 1
        entry = task.find_entry(title='bla.s01.720p-flexget')
        assert entry.accepted

    def test_proper_season_pack(self, execute_task):
        """Series plugin: proper available immediately"""
        task = execute_task('test_proper_season_pack')
        assert task.find_entry('accepted', title='foo.s01.720p.proper-flexget')

    def test_proper_season_pack_2(self, execute_task):
        """Series plugin: proper available immediately"""
        task = execute_task('test_proper_season_pack_2')
        assert task.find_entry('accepted', title='foo.s01.720p-flexget')

        task = execute_task('test_proper_season_pack_3')
        assert task.find_entry('accepted', title='foo.s01.720p.proper-flexget')

    def test_all_series(self, execute_task):
        task = execute_task('test_all_series')
        assert task.find_entry('accepted', title='show.name.s01.720p.HDTV-Group')

    def test_advanced_config(self, execute_task):
        task = execute_task('test_with_dict_config_1')
        assert not task.find_entry('accepted', title='bro.s01e01.720p.HDTV-Flexget')
        assert task.find_entry('accepted', title='bro.s01.720p.HDTV-Flexget')

        execute_task('test_with_dict_config_2',
                     options={'inject': [Entry(title='bro.s02e01.720p.HDTV-Flexget', url='')],
                              'immortal': True})

        task = execute_task('test_with_dict_config_2')
        assert task.find_entry('accepted', title='bro.s02.720p.HDTV-Flexget')
