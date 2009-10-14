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
        s = self.parse(name='Something Interesting', data='Something.Interesting.S01E02.Proper-FlexGet')
        assert s.season == 1
        assert s.episode == 2
        assert s.quality == 'unknown'
        assert s.proper_or_repack, 'did not detect proper from %s' % s.data

        s = self.parse(name='foobar', data='foobar 720p proper s01e01')
        assert s.proper_or_repack, 'did not detect proper from %s' % s.data


    def test_non_proper(self):
        s = self.parse(name='Something Interesting', data='Something.Interesting.S01E02-FlexGet')
        assert s.season == 1
        assert s.episode == 2
        assert s.quality == 'unknown'
        assert not s.proper_or_repack, 'detected proper'

    def test_basic(self):
        s = self.parse(name='Something Interesting', data='The.Something.Interesting.S01E02-FlexGet')
        assert not s.valid, 'Should not be valid'

        s = self.parse(name='25', data='25.And.More.S01E02-FlexGet')
        assert s.valid, 'Fix the implementation, should not be valid'

    def test_invalid_name(self):
        s = SeriesParser()
        s.name = 1
        s.data = 'Something'
        assert_raises(Exception, s.parse)

    def test_invalid_data(self):
        s = SeriesParser()
        s.name = 'Something Interesting'
        s.data = 1
        assert_raises(Exception, s.parse)

    def test_confusing(self):
        s = self.parse(name='Something', data='Something.2008x12.13-FlexGet')
        assert not s.episode, 'Should not have episode'
        assert not s.season, 'Should not have season'
        assert s.id == '2008-12-13', 'invalid id'
        assert s.valid, 'should not valid'

    def test_SxE(self):
        # Test 01x02 format
        s = self.parse(name='Something', data='Something.01x02-FlexGet')
        assert (s.season==1 and s.episode==2), 'failed to parse 01x02'

        s = self.parse(name='Something', data='Something 1 x 2-FlexGet')
        assert (s.season==1 and s.episode==2), 'failed to parse 1 x 2'

    def test_digits(self):
        s = self.parse(name='Something', data='Something 01 FlexGet')
        assert (s.id=='01'), 'failed to parse %s' % s.data

        s = self.parse(name='Something', data='Something-121.H264.FlexGet')
        assert (s.id=='121'), 'failed to parse %s' % s.data

    def test_quality(self):
        s = self.parse(name='Foo Bar', data='Foo.Bar.S01E01.720p.HDTV.x264-FlexGet')
        assert (s.season==1 and s.episode==1), 'failed to parse episodes from %s' % s.data
        assert (s.quality=='720p'), 'failed to parse quality from %s' % s.data

        s = self.parse(name='Test', data='Test.S01E01.720p-FlexGet')
        assert s.quality=='720p', 'failed to parse quality from %s' % s.data

    def test_quality_parenthesis(self):
        s = self.parse(name='Foo Bar', data='Foo.Bar.S01E01.[720p].HDTV.x264-FlexGet')
        assert (s.season==1 and s.episode==1), 'failed to parse episodes from %s' % s.data
        assert (s.quality=='720p'), 'failed to parse quality from %s' % s.data

        s = self.parse(name='Foo Bar', data='Foo.Bar.S01E01.(720p).HDTV.x264-FlexGet')
        assert (s.season==1 and s.episode==1), 'failed to parse episodes from %s' % s.data
        assert (s.quality=='720p'), 'failed to parse quality from %s' % s.data

    def test_numeric_names(self):
        s = self.parse(name='24', data='24.1x2-FlexGet')
        assert (s.season==1 and s.episode==2), 'failed to parse %s' % s.data

        s = self.parse(name='90120', data='90120.1x2-FlexGet')
        assert (s.season==1 and s.episode==2), 'failed to parse %s' % s.data

        s = self.parse(name='Foo Bar', data='[l.u.l.z] Foo Bar - 11 (H.264) [5235532D].mkv')
        assert (s.id=='11'), 'failed to parse %s' % s.data

        s = self.parse(name='Foo Bar', data='[7.1.7.5] Foo Bar - 11 (H.264) [5235532D].mkv')
        assert (s.id=='11'), 'failed to parse %s' % s.data

    def test_partially_numeric(self):
        s = self.parse(name='Foo 2009', data='Foo.2009.S02E04.HDTV.XviD-2HD[FlexGet]')
        assert (s.season==2 and s.episode==4), 'failed to parse %s' % s.data
        assert (s.quality=='hdtv'), 'failed to parse quality from %s' % s.data

    def test_seasonpacks(self):
        s = SeriesParser()
        s.name = 'Something'
        s.data = 'Something S02 Pack 720p WEB-DL-FlexGet'
        assert_raises(ParseWarning, s.parse)

    def test_similar(self):
        pass
        """
        s = self.parse(name='Foo Bar', data='Foo.Bar:Doppelganger.S02E04.HDTV.FlexGet')
        assert not s.valid, 'should not have parser Foo.Bar:Doppelganger'
        s = self.parse(name='Foo Bar', data='Foo.Bar.Doppelganger.S02E04.HDTV.FlexGet')
        assert not s.valid, 'should not have parser Foo.Bar.Doppelganger'
        """
