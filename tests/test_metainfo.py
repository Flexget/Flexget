from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase


class TestMetainfo(FlexGetBase):

    __yaml__ = """
        tasks:
          test_quality:
            mock:
              - {title: 'test quality', description: 'metainfo quality should parse quality 720p from this'}
          test_content_size:
            mock:
              - {title: 'size 10MB', description: 'metainfo content size should parse size 10.2MB from this'}
              - {title: 'size 200MB', description: 'metainfo content size should parse size 200MB from this'}
              - {title: 'size 1024MB', description: 'metainfo content size should parse size 1.0GB from this'}
    """

    def test_quality(self):
        """Metainfo: parse quality"""
        self.execute_task('test_quality')
        assert self.task.find_entry(quality='720p'), 'Quality not parsed'

    def test_content_size(self):
        """Metainfo: parse content size"""
        self.execute_task('test_content_size')
        assert self.task.find_entry(content_size=10), 'Content size 10 MB absent'
        assert self.task.find_entry(content_size=200), 'Content size 200 MB absent'
        assert self.task.find_entry(content_size=1024), 'Content size 1024 MB absent'


class TestMetainfoImdb(FlexGetBase):

    __yaml__ = """
        tasks:
          test:
            mock:
              - {title: 'Scan Test 1', description: 'title: Foo Bar Asdf\n imdb-url: http://www.imdb.com/title/tt0330793/ more text'}
              - {title: 'Scan Test 2', description: '<a href="http://imdb.com/title/tt0472198/">IMDb</a>'}
              - {title: 'Scan Test 3', description: 'nothing here'}
              - {title: 'Scan Test 4', description: 'imdb.com/title/tt66666 http://imdb.com/title/tt99999'}
    """

    def test_imdb(self):
        """Metainfo: imdb url"""
        self.execute_task('test')
        assert self.task.find_entry(imdb_url='http://www.imdb.com/title/tt0330793/'), \
            'Failed to pick url from test 1'
        assert self.task.find_entry(imdb_url='http://www.imdb.com/title/tt0472198/'), \
            'Failed to pick url from test 2'
        assert not self.task.find_entry(imdb_url='http://www.imdb.com/title/tt66666/'), \
            'Failed to ignore multiple imdb urls in test 4'
        assert not self.task.find_entry(imdb_url='http://www.imdb.com/title/tt99999/'), \
            'Failed to ignore multiple imdb urls in test 4'


class TestMetainfoQuality(FlexGetBase):

    __yaml__ = """
        tasks:
          test:
            mock:
              - {title: 'FooBar.S01E02.720p.HDTV'}
              - {title: 'ShowB.S04E19.Name of Ep.720p.WEB-DL.DD5.1.H.264'}
              - {title: 'Good.Movie', description: '720p'}
              - {title: 'Good.Movie.hdtv', description: '720p'}
    """

    def test_quality(self):
        self.execute_task('test')
        entry = self.task.find_entry(title='FooBar.S01E02.720p.HDTV')
        assert entry, 'entry not found?'
        assert 'quality' in entry, 'failed to pick up quality'
        assert entry['quality'].name == '720p hdtv', 'picked up wrong quality %s' % entry.get('quality', None)
        entry = self.task.find_entry(title='ShowB.S04E19.Name of Ep.720p.WEB-DL.DD5.1.H.264')
        assert entry, 'entry not found?'
        assert 'quality' in entry, 'failed to pick up quality'
        assert entry['quality'].name == '720p webdl h264 dd5.1', 'picked up wrong quality %s' % entry.get('quality', None)
        # Check that quality gets picked up from description when not in title
        entry = self.task.find_entry(title='Good.Movie')
        assert 'quality' in entry, 'failed to pick up quality from description'
        assert entry['quality'].name == '720p', 'picked up wrong quality %s' % entry.get('quality', None)
        # quality in description should not override one found in title
        entry = self.task.find_entry(title='Good.Movie.hdtv')
        assert 'quality' in entry, 'failed to pick up quality'
        assert entry['quality'].name == 'hdtv', 'picked up wrong quality %s' % entry.get('quality', None)


class TestMetainfoSeries(FlexGetBase):
    __yaml__ = """
        presets:
          global:
            metainfo_series: yes
        tasks:
          test:
            mock:
              - {title: 'FlexGet.S01E02.TheName.HDTV.xvid'}
              - {title: 'some.series.S03E14.Title.Here.720p'}
              - {title: '[the.group] Some.Series.S03E15.Title.Two.720p'}
              - {title: 'HD 720p: Some series.S03E16.Title.Three'}
              - {title: 'Something.Season.2.1of4.Ep.Title.HDTV.torrent'}
              - {title: 'Show-A (US) - Episode Title S02E09 hdtv'}
              - {title: "Jack's.Show.S03E01.blah.1080p"}
          false_positives:
            mock:
              - {title: 'FlexGet.epic'}
              - {title: 'FlexGet.Apt.1'}
              - {title: 'FlexGet.aptitude'}
              - {title: 'FlexGet.Step1'}
              - {title: 'Something.1x0.Complete.Season-FlexGet'}
              - {title: 'Something.1xAll.Season.Complete-FlexGet'}
              - {title: 'Something Seasons 1 & 2 - Complete'}
              - {title: 'Something Seasons 4 Complete'}
              - {title: 'Something.S01D2.DVDR-FlexGet'}
    """

    def test_metainfo_series(self):
        """Metainfo series: name/episode"""
        # We search for series name in title case to make sure case is being normalized
        self.execute_task('test')
        assert self.task.find_entry(series_name='Flexget', series_season=1, series_episode=2, quality='hdtv xvid'), \
            'Failed to parse series info'
        assert self.task.find_entry(series_name='Some Series', series_season=3, series_episode=14, quality='720p'), \
            'Failed to parse series info'
        assert self.task.find_entry(series_name='Something', series_season=2, series_episode=1, quality='hdtv'), \
            'Failed to parse series info'
        # Test unwanted prefixes get stripped from series name
        assert self.task.find_entry(series_name='Some Series', series_season=3, series_episode=15, quality='720p'), \
            'Failed to parse series info'
        assert self.task.find_entry(series_name='Some Series', series_season=3, series_episode=16, quality='720p'), \
            'Failed to parse series info'
        # Test episode title and parentheses are stripped from series name
        assert self.task.find_entry(series_name='Show-a Us', series_season=2, series_episode=9, quality='hdtv'), \
            'Failed to parse series info'
        assert self.task.find_entry(series_name='Jack\'s Show', series_season=3, series_episode=1, quality='1080p'), \
            'Failed to parse series info'

    def test_false_positives(self):
        """Metainfo series: check for false positives"""
        self.execute_task('false_positives')
        for entry in self.task.entries:
            # None of these should be detected as series
            error = '%s sholud not be detected as a series' % entry['title']
            assert 'series_name' not in entry, error
            assert 'series_guessed' not in entry, error
            assert 'series_parser' not in entry, error
