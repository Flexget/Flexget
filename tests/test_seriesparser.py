from nose.tools import assert_raises
from flexget.utils.titles import SeriesParser, ParseWarning


class TestSeriesParser(object):

    def parse(self, **kwargs):
        s = SeriesParser()
        s.name = kwargs['name']
        s.data = kwargs['data']
        s.parse()
        return s

    def test_proper(self):
        """SeriesParser: proper"""
        s = self.parse(name='Something Interesting', data='Something.Interesting.S01E02.Proper-FlexGet')
        assert s.season == 1
        assert s.episode == 2
        assert s.quality == 'unknown'
        assert s.proper_or_repack, 'did not detect proper from %s' % s.data
        s = self.parse(name='foobar', data='foobar 720p proper s01e01')
        assert s.proper_or_repack, 'did not detect proper from %s' % s.data

    def test_non_proper(self):
        """SeriesParser: non-proper"""
        s = self.parse(name='Something Interesting', data='Something.Interesting.S01E02-FlexGet')
        assert s.season == 1
        assert s.episode == 2
        assert s.quality == 'unknown'
        assert not s.proper_or_repack, 'detected proper'

    def test_basic(self):
        """SeriesParser: basic parsing"""
        s = self.parse(name='Something Interesting', data='The.Something.Interesting.S01E02-FlexGet')
        assert not s.valid, 'Should not be valid'

        s = self.parse(name='25', data='25.And.More.S01E02-FlexGet')
        assert s.valid, 'Fix the implementation, should not be valid'
        assert s.identifier == 'S01E02', 'identifier broken'

    def test_invalid_name(self):
        """SeriesParser: invalid name"""
        s = SeriesParser()
        s.name = 1
        s.data = 'Something'
        assert_raises(Exception, s.parse)

    def test_invalid_data(self):
        """SeriesParser: invalid data"""
        s = SeriesParser()
        s.name = 'Something Interesting'
        s.data = 1
        assert_raises(Exception, s.parse)

    def test_confusing(self):
        """SeriesParser: confusing (invalid) numbering scheme"""
        s = self.parse(name='Something', data='Something.2008x12.13-FlexGet')
        assert not s.episode, 'Should not have episode'
        assert not s.season, 'Should not have season'
        assert s.id == '2008-12-13', 'invalid id'
        assert s.valid, 'should not valid'

    def test_season_x_ep(self):
        """SeriesParser: 01x02"""
        # Test 01x02 format
        s = self.parse(name='Something', data='Something.01x02-FlexGet')
        assert (s.season == 1 and s.episode == 2), 'failed to parse 01x02'

        s = self.parse(name='Something', data='Something 1 x 2-FlexGet')
        assert (s.season == 1 and s.episode == 2), 'failed to parse 1 x 2'

    def test_digits(self):
        """SeriesParser: digits (UID)"""
        s = self.parse(name='Something', data='Something 01 FlexGet')
        assert (s.id == '01'), 'failed to parse %s' % s.data

        s = self.parse(name='Something', data='Something-121.H264.FlexGet')
        assert (s.id == '121'), 'failed to parse %s' % s.data

    def test_quality(self):
        """SeriesParser: quality"""
        s = self.parse(name='Foo Bar', data='Foo.Bar.S01E01.720p.HDTV.x264-FlexGet')
        assert (s.season == 1 and s.episode == 1), 'failed to parse episodes from %s' % s.data
        assert (s.quality == '720p'), 'failed to parse quality from %s' % s.data

        s = self.parse(name='Test', data='Test.S01E01.720p-FlexGet')
        assert s.quality == '720p', 'failed to parse quality from %s' % s.data

        s = self.parse(name='30 Suck', data='30 Suck 4x4 [HDTV - FlexGet]')
        assert s.quality == 'hdtv', 'failed to parse quality %s' % s

    def test_quality_parenthesis(self):
        """SeriesParser: quality in parenthesis"""
        s = self.parse(name='Foo Bar', data='Foo.Bar.S01E01.[720p].HDTV.x264-FlexGet')
        assert (s.season == 1 and s.episode == 1), 'failed to parse episodes from %s' % s.data
        assert (s.quality == '720p'), 'failed to parse quality from %s' % s.data

        s = self.parse(name='Foo Bar', data='Foo.Bar.S01E01.(720p).HDTV.x264-FlexGet')
        assert (s.season == 1 and s.episode == 1), 'failed to parse episodes from %s' % s.data
        assert (s.quality == '720p'), 'failed to parse quality from %s' % s.data

    def test_numeric_names(self):
        """SeriesParser: numeric names (24)"""
        s = self.parse(name='24', data='24.1x2-FlexGet')
        assert (s.season == 1 and s.episode == 2), 'failed to parse %s' % s.data

        s = self.parse(name='90120', data='90120.1x2-FlexGet')
        assert (s.season == 1 and s.episode == 2), 'failed to parse %s' % s.data

        s = self.parse(name='Foo Bar', data='[l.u.l.z] Foo Bar - 11 (H.264) [5235532D].mkv')
        assert (s.id == '11'), 'failed to parse %s' % s.data

        s = self.parse(name='Foo Bar', data='[7.1.7.5] Foo Bar - 11 (H.264) [5235532D].mkv')
        assert (s.id == '11'), 'failed to parse %s' % s.data

    def test_partially_numeric(self):
        """SeriesParser: partially numeric names"""
        s = self.parse(name='Foo 2009', data='Foo.2009.S02E04.HDTV.XviD-2HD[FlexGet]')
        assert (s.season == 2 and s.episode == 4), 'failed to parse %s' % s.data
        assert (s.quality == 'hdtv'), 'failed to parse quality from %s' % s.data

    def test_ignore_seasonpacks(self):
        """SeriesParser: ignoring season packs"""
        """
        s = SeriesParser()
        s.name = 'The Foo'
        s.expect_ep = False
        s.data = 'The.Foo.S04.1080p.FlexGet.5.1'
        assert_raises(ParseWarning, s.parse)
        """

        s = SeriesParser()
        s.name = 'Something'
        s.data = 'Something S02 Pack 720p WEB-DL-FlexGet'
        assert_raises(ParseWarning, s.parse)

        s = SeriesParser()
        s.name = 'The Foo'
        s.expect_ep = False
        s.data = 'The Foo S05 720p BluRay DTS x264-FlexGet'
        assert_raises(ParseWarning, s.parse)

        s = SeriesParser()
        s.name = 'The Foo'
        s.expect_ep = True
        s.data = 'The Foo S05 720p BluRay DTS x264-FlexGet'
        assert_raises(ParseWarning, s.parse)

    def _test_similar(self):
        pass
        """
        s = self.parse(name='Foo Bar', data='Foo.Bar:Doppelganger.S02E04.HDTV.FlexGet')
        assert not s.valid, 'should not have parser Foo.Bar:Doppelganger'
        s = self.parse(name='Foo Bar', data='Foo.Bar.Doppelganger.S02E04.HDTV.FlexGet')
        assert not s.valid, 'should not have parser Foo.Bar.Doppelganger'
        """

    def test_idiotic_numbering(self):
        """SeriesParser: idiotic 101, 102, 103, .. numbering"""
        s = SeriesParser()
        s.name = 'test'
        s.data = 'Test.706.720p-FlexGet'
        s.expect_ep = True
        s.parse()
        assert s.season == 7, 'didn''t pick up season'
        assert s.episode == 6, 'didn''t pick up episode'

    def test_idiotic_numbering_with_zero(self):
        """SeriesParser: idiotic 0101, 0102, 0103, .. numbering"""
        s = SeriesParser()
        s.name = 'test'
        s.data = 'Test.0706.720p-FlexGet'
        s.expect_ep = True
        s.parse()
        assert s.season == 7, 'season missing'
        assert s.episode == 6, 'episode missing'
        assert s.identifier == 'S07E06', 'identifier broken'

    def test_exact_name(self):
        """SeriesParser: test exact/strict name parsing"""

        s = SeriesParser()
        s.name = 'test'
        s.data = 'Test.Foobar.S01E02.720p-FlexGet'
        s.parse()
        assert s.valid, 'normal failed'

        s = SeriesParser()
        s.strict_name = True
        s.name = 'test'
        s.data = 'Test.A.S01E02.720p-FlexGet'
        s.parse()
        assert not s.valid, 'strict failed'

        s = SeriesParser()
        s.strict_name = True
        s.name = 'Test AB'
        s.data = 'Test.AB.S01E02.720p-FlexGet'
        s.parse()
        assert s.valid, 'strict AB failed'
