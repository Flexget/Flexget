from tests import FlexGetBase


class TestMetainfo(FlexGetBase):

    __yaml__ = """
        feeds:
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
        self.execute_feed('test_quality')
        assert self.feed.find_entry(quality='720p'), 'Quality not parsed'

    def test_content_size(self):
        """Metainfo: parse content size"""
        self.execute_feed('test_content_size')
        assert self.feed.find_entry(content_size=10), 'Content size 10 MB absent'
        assert self.feed.find_entry(content_size=200), 'Content size 200 MB absent'
        assert self.feed.find_entry(content_size=1024), 'Content size 1024 MB absent'


class TestMetainfoImdb(FlexGetBase):

    __yaml__ = """
        feeds:
          test:
            mock:
              - {title: 'Scan Test 1', description: 'title: Foo Bar Asdf\n imdb-url: http://www.imdb.com/title/tt0330793/ more text'}
              - {title: 'Scan Test 2', description: '<a href="http://imdb.com/title/tt0472198/">IMDb</a>'}
              - {title: 'Scan Test 3', description: 'nothing here'}
              - {title: 'Scan Test 4', description: 'imdb.com/title/tt66666 http://imdb.com/title/tt99999'}
    """

    def test_imdb(self):
        """Metainfo: imdb url"""
        self.execute_feed('test')
        assert self.feed.find_entry(imdb_url='http://www.imdb.com/title/tt0330793/'), \
            'Failed to pick url from test 1'
        assert self.feed.find_entry(imdb_url='http://www.imdb.com/title/tt0472198/'), \
            'Failed to pick url from test 2'
        assert not self.feed.find_entry(imdb_url='http://www.imdb.com/title/tt66666/'), \
            'Failed to ignore multiple imdb urls in test 4'
        assert not self.feed.find_entry(imdb_url='http://www.imdb.com/title/tt99999/'), \
            'Failed to ignore multiple imdb urls in test 4'


class TestMetainfoQuality(FlexGetBase):

    __yaml__ = """
        feeds:
          test:
            mock:
              - {title: 'FooBar.S01E02.720p.HDTV'}
              - {title: 'ShowB.S04E19.Name of Ep.720p.WEB-DL.DD5.1.H.264'}
    """

    def test_quality(self):
        self.execute_feed('test')
        entry = self.feed.find_entry(title='FooBar.S01E02.720p.HDTV')
        assert entry, 'entry not found?'
        assert 'quality' in entry, 'failed to pick up quality'
        assert entry['quality'] == '720p', 'picked up wrong quality %s' % entry.get('quality', None)
        entry = self.feed.find_entry(title='ShowB.S04E19.Name of Ep.720p.WEB-DL.DD5.1.H.264')
        assert entry, 'entry not found?'
        assert 'quality' in entry, 'failed to pick up quality'
        assert entry['quality'] == 'web-dl', 'picked up wrong quality %s' % entry.get('quality', None)


class TestMetainfoSeries(FlexGetBase):
    __yaml__ = """
        feeds:
          test:
            mock:
              - {title: 'FlexGet.S01E02.TheName.HDTV.xvid'}
              - {title: 'Some.Series.S03E14.Title.Here.720p'}
              - {title: '[the.group] Some.Series.S03E15.Title.Two.720p'}
              - {title: 'HD 720p: Some.Series.S03E16.Title.Three'}
    """

    def test_imdb(self):
        """Metainfo: series name/episode"""
        self.execute_feed('test')
        assert self.feed.find_entry(series_name='FlexGet', series_season=1, series_episode=2, quality='hdtv'), \
            'Failed to parse series info'
        assert self.feed.find_entry(series_name='Some Series', series_season=3, series_episode=14, quality='720p'), \
            'Failed to parse series info'
        # Test unwanted prefixes get stripped from series name
        assert self.feed.find_entry(series_name='Some Series', series_season=3, series_episode=15, quality='720p'), \
            'Failed to parse series info'
        assert self.feed.find_entry(series_name='Some Series', series_season=3, series_episode=16, quality='720p'), \
            'Failed to parse series info'
