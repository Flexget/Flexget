from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import pytest


class TestMetainfo(object):
    config = """
        tasks:
          test_content_size:
            mock:
              - {title: 'size 10MB', description: 'metainfo content size should parse size 10.2MB from this'}
              - {title: 'size 200MB', description: 'metainfo content size should parse size 200MB from this'}
              - {title: 'size 1024MB', description: 'metainfo content size should parse size 1.0GB from this'}
    """

    def test_content_size(self, execute_task):
        """Metainfo: parse content size"""
        task = execute_task('test_content_size')
        assert task.find_entry(content_size=10), 'Content size 10 MB absent'
        assert task.find_entry(content_size=200), 'Content size 200 MB absent'
        assert task.find_entry(content_size=1024), 'Content size 1024 MB absent'


class TestMetainfoImdb(object):
    config = """
        tasks:
          test:
            mock:
              - {title: 'Scan Test 1',
                  description: 'title: Foo Bar Asdf\n imdb-url: http://www.imdb.com/title/tt0330793/ more text'}
              - {title: 'Scan Test 2', description: '<a href="http://imdb.com/title/tt0472198/">IMDb</a>'}
              - {title: 'Scan Test 3', description: 'nothing here'}
              - {title: 'Scan Test 4', description: 'imdb.com/title/tt66666 http://imdb.com/title/tt99999'}
    """

    def test_imdb(self, execute_task):
        """Metainfo: imdb url"""
        task = execute_task('test')
        assert task.find_entry(imdb_url='http://www.imdb.com/title/tt0330793/'), \
            'Failed to pick url from test 1'
        assert task.find_entry(imdb_url='http://www.imdb.com/title/tt0472198/'), \
            'Failed to pick url from test 2'
        assert not task.find_entry(imdb_url='http://www.imdb.com/title/tt66666/'), \
            'Failed to ignore multiple imdb urls in test 4'
        assert not task.find_entry(imdb_url='http://www.imdb.com/title/tt99999/'), \
            'Failed to ignore multiple imdb urls in test 4'


class TestMetainfoQuality(object):
    config = """
        tasks:
          test:
            mock:
              - {title: 'FooBar.S01E02.720p.HDTV'}
              - {title: 'ShowB.S04E19.Name of Ep.720p.WEB-DL.DD5.1.H.264'}
              - {title: 'Good.Movie.hdtv', description: '720p'}
    """

    def test_quality(self, execute_task):
        task = execute_task('test')
        entry = task.find_entry(title='FooBar.S01E02.720p.HDTV')
        assert entry, 'entry not found?'
        assert 'quality' in entry, 'failed to pick up quality'
        assert entry['quality'].name == '720p hdtv', 'picked up wrong quality %s' % entry.get('quality', None)
        entry = task.find_entry(title='ShowB.S04E19.Name of Ep.720p.WEB-DL.DD5.1.H.264')
        assert entry, 'entry not found?'
        assert 'quality' in entry, 'failed to pick up quality'
        assert entry['quality'].name == '720p webdl h264 dd5.1', \
            'picked up wrong quality %s' % entry.get('quality', None)
        # quality in description should not override one found in title
        entry = task.find_entry(title='Good.Movie.hdtv')
        assert 'quality' in entry, 'failed to pick up quality'
        assert entry['quality'].name == 'hdtv', 'picked up wrong quality %s' % entry.get('quality', None)


class TestMetainfoSeries(object):
    _config = """
        templates:
          global:
            parsing:
              series: __parser__
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
              - {title: 'Something Seasons 1 & 2 - Complete'}
              - {title: 'Something Seasons 4 Complete'}
              - {title: 'Something.S01D2.DVDR-FlexGet'}
    """

    @pytest.fixture(scope='class', params=['internal', 'guessit'], ids=['internal', 'guessit'])
    def config(self, request):
        """Override and parametrize default config fixture for all series tests."""
        return self._config.replace('__parser__', request.param)

    def test_metainfo_series(self, execute_task):
        """Metainfo series: name/episode"""
        # We search for series name in title case to make sure case is being normalized
        task = execute_task('test')
        assert task.find_entry(series_name='Flexget', series_season=1, series_episode=2, quality='hdtv xvid'), \
            'Failed to parse series info'
        assert task.find_entry(series_name='Some Series', series_season=3, series_episode=14, quality='720p'), \
            'Failed to parse series info'
        assert task.find_entry(series_name='Something', series_season=2, series_episode=1, quality='hdtv'), \
            'Failed to parse series info'
        # Test unwanted prefixes get stripped from series name
        assert task.find_entry(series_name='Some Series', series_season=3, series_episode=15, quality='720p'), \
            'Failed to parse series info'
        assert task.find_entry(series_name='Some Series', series_season=3, series_episode=16, quality='720p'), \
            'Failed to parse series info'
        # Test episode title and parentheses are stripped from series name
        assert task.find_entry(series_name='Show-a Us', series_season=2, series_episode=9, quality='hdtv'), \
            'Failed to parse series info'
        assert task.find_entry(series_name='Jack\'s Show', series_season=3, series_episode=1, quality='1080p'), \
            'Failed to parse series info'

    def test_false_positives(self, execute_task):
        """Metainfo series: check for false positives"""
        task = execute_task('false_positives')
        for entry in task.entries:
            # None of these should be detected as series
            error = '%s should not be detected as a series' % entry['title']
            assert 'series_name' not in entry, error
            assert 'series_guessed' not in entry, error
            assert 'series_parser' not in entry, error


class TestMetainfoMovie(object):
    config = """
        templates:
          global:
            metainfo_movie: yes
        tasks:
          test:
            mock:
              - {title: 'FlexGet.720p.HDTV.xvid-TheName'}
              - {title: 'FlexGet2 (1999).720p.HDTV.xvid-TheName'}
              - {title: 'FlexGet3 (2004).PROPER.1080p.BluRay.xvid-TheName'}
          test_guessit:
            parsing:
              movie: guessit
            mock:
              - {title: 'FlexGet.720p.HDTV.xvid-TheName'}
              - {title: 'FlexGet3 (2004).PROPER.1080p.BluRay.xvid-TheName'}
              - {title: 'The.Flexget.2000.BluRay.Remux.1080p.AVC.TrueHD.5.1-FQ'}
              - {title: 'The.Flexget.Winters.War.2016.1080p.WEB-DL.H264.AC3-FlexO'}
    """

    def test_metainfo_movie(self, execute_task):
        task = execute_task('test')
        assert task.find_entry(movie_name='Flexget',
                               quality='720p hdtv xvid')
        assert task.find_entry(movie_name='Flexget2',
                               movie_year=1999,
                               quality='720p hdtv xvid')
        assert task.find_entry(movie_name='Flexget3',
                               movie_year=2004,
                               proper=True,
                               quality='1080p BluRay xvid')

    def test_metainfo_movie_with_guessit(self, execute_task):
        task = execute_task('test_guessit')
        assert task.find_entry(movie_name='Flexget',
                               format='HDTV',
                               screen_size='720p',
                               video_codec='XviD',
                               release_group='TheName')

        assert task.find_entry(movie_name='Flexget3',
                               movie_year=2004,
                               proper=True,
                               format='BluRay',
                               screen_size='1080p',
                               video_codec='XviD',
                               release_group='TheName')

        assert task.find_entry(movie_name='The Flexget',
                               audio_channels='5.1',
                               audio_codec='TrueHD',
                               movie_year=2000,
                               format='BluRay',
                               screen_size='1080p',
                               release_group='FQ')

        assert task.find_entry(movie_name='The Flexget Winters War',
                               audio_codec='AC3',
                               movie_year=2016,
                               format='WEB-DL',
                               screen_size='1080p',
                               video_codec='h264',
                               release_group='FlexO')
