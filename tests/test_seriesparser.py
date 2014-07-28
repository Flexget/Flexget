# -*- coding: utf-8 -*-

from __future__ import unicode_literals, division, absolute_import
from nose.tools import assert_raises, raises
from flexget.utils.titles import SeriesParser, ParseWarning

#
# NOTE:
#
# Logging doesn't properly work if you run this test only as it is initialized
# in FlexGetBase which this does NOT use at all. I spent hour debugging why
# logging doesn't work ...
#

# try to get logging running ...
# enable enable_logging and add --nologcapture to nosetest to see debug
# (should not be needed, logging is not initialized properly?)

enable_logging = True

if enable_logging:
    #level = 5
    #import logging
    import flexget.logger
    flexget.logger.initialize(True)
    ##log = logging.getLogger()
    ##log.setLevel(level)
    # switch seriesparser logging to debug
    import tests
    from flexget.utils.titles.series import log as parser_log
    parser_log.setLevel(tests.setup_logging_level())


class TestSeriesParser(object):

    def parse(self, name, data, **kwargs):
        s = SeriesParser(name, **kwargs)
        s.parse(data)
        return s

    def parse_invalid(self, name, data, **kwargs):
        """Makes sure either ParseWarning is raised, or return is invalid."""
        try:
            r = self.parse(name, data, **kwargs)
            assert not r.valid, '{data} should not be valid'.format(data=data)
        except ParseWarning:
            pass

    def test_proper(self):
        """SeriesParser: proper"""
        s = self.parse(name='Something Interesting', data='Something.Interesting.S01E02.Proper-FlexGet')
        assert s.season == 1
        assert s.episode == 2
        assert s.quality.name == 'unknown'
        assert s.proper, 'did not detect proper from %s' % s.data
        s = self.parse(name='foobar', data='foobar 720p proper s01e01')
        assert s.proper, 'did not detect proper from %s' % s.data

    def test_non_proper(self):
        """SeriesParser: non-proper"""
        s = self.parse(name='Something Interesting', data='Something.Interesting.S01E02-FlexGet')
        assert s.season == 1
        assert s.episode == 2
        assert s.quality.name == 'unknown'
        assert not s.proper, 'detected proper'

    def test_anime_proper(self):
        """SeriesParser: anime fansub style proper (13v2)"""
        s = self.parse(name='Anime', data='[aoeu] Anime 19v2 [23BA98]')
        assert s.identifier == 19
        assert s.proper_count == 1
        s = self.parse(name='Anime', data='Anime_-_19v3')
        assert s.identifier == 19
        assert s.proper_count == 2

    def test_basic(self):
        """SeriesParser: basic parsing"""
        s = self.parse(name='Something Interesting', data='The.Something.Interesting.S01E02-FlexGet')
        assert not s.valid, 'Should not be valid'

        s = self.parse(name='25', data='25.And.More.S01E02-FlexGet')
        assert s.valid, 'Fix the implementation, should be valid'
        assert s.identifier == 'S01E02', 'identifier broken'

    @raises(Exception)
    def test_invalid_name(self):
        """SeriesParser: invalid name"""
        s = SeriesParser()
        s.name = 1
        s.data = 'Something'

    @raises(Exception)
    def test_invalid_data(self):
        """SeriesParser: invalid data"""
        s = SeriesParser()
        s.name = 'Something Interesting'
        s.data = 1

    def test_confusing_date(self):
        """SeriesParser: confusing (invalid) numbering scheme"""
        s = self.parse(name='Something', data='Something.2008x12.13-FlexGet')
        assert not s.episode, 'Should not have episode'
        assert not s.season, 'Should not have season'
        assert s.id_type == 'date'
        assert s.identifier == '2008-12-13', 'invalid id'
        assert s.valid, 'should be valid'

    def test_unwanted_disc(self):
        """SeriesParser: unwanted disc releases"""
        self.parse_invalid(name='Something', data='Something.S01D2.DVDR-FlexGet')

    def test_season_x_ep(self):
        """SeriesParser: 01x02"""
        s = self.parse(name='Something', data='Something.01x02-FlexGet')
        assert (s.season == 1 and s.episode == 2), 'failed to parse 01x02'

        s = self.parse(name='Something', data='Something 1 x 2-FlexGet')
        assert (s.season == 1 and s.episode == 2), 'failed to parse 1 x 2'

        # Ticket #732
        s = self.parse(name='Something', data='Something - This is the Subtitle 14x9 [Group-Name]')
        assert (s.season == 14 and s.episode == 9), 'failed to parse %s' % s.data

    def test_ep_in_square_brackets(self):
        """SeriesParser: [S01] [E02] NOT IMPLEMENTED"""
        return

        # FIX: #402 .. a bit hard to do
        s = self.parse(name='Something', data='Something [S01] [E02]')
        assert (s.season == 1 and s.episode == 2), 'failed to parse %s' % s

    def test_ep_in_parenthesis(self):
        """SeriesParser: test ep in parenthesis"""
        s = self.parse(name='Something', data='Something (S01E02)')
        assert (s.season == 1 and s.episode == 2), 'failed to parse %s' % s

    def test_season_episode(self):
        """SeriesParser: season X, episode Y"""
        s = self.parse(name='Something', data='Something - Season 3, Episode 2')
        assert (s.season == 3 and s.episode == 2), 'failed to parse %s' % s

        s = self.parse(name='Something', data='Something - Season2, Episode2')
        assert (s.season == 2 and s.episode == 2), 'failed to parse %s' % s

        s = self.parse(name='Something', data='Something - Season2 Episode2')
        assert (s.season == 2 and s.episode == 2), 'failed to parse %s' % s

    def test_series_episode(self):
        """SeriesParser: series X, episode Y"""
        s = self.parse(name='Something', data='Something - Series 2, Episode 2')
        assert (s.season == 2 and s.episode == 2), 'failed to parse %s' % s

        s = self.parse(name='Something', data='Something - Series3, Episode2')
        assert (s.season == 3 and s.episode == 2), 'failed to parse %s' % s

        s = self.parse(name='Something', data='Something - Series4 Episode2')
        assert (s.season == 4 and s.episode == 2), 'failed to parse %s' % s

    def test_episode(self):
        """SeriesParser: episode X (assume season 1)"""
        s = self.parse(name='Something', data='Something - Episode2')
        assert (s.season == 1 and s.episode == 2), 'failed to parse %s' % s

        s = self.parse(name='Something', data='Something - Episode 2')
        assert (s.season == 1 and s.episode == 2), 'failed to parse %s' % s

        s = self.parse(name='Something', data='Something - Episode VIII')
        assert (s.season == 1 and s.episode == 8), 'failed to parse %s' % s

    def test_ep(self):
        """SeriesParser: ep X (assume season 1)"""
        s = self.parse(name='Something', data='Something - Ep2')
        assert (s.season == 1 and s.episode == 2), 'failed to parse %s' % s

        s = self.parse(name='Something', data='Something - Ep 2')
        assert (s.season == 1 and s.episode == 2), 'failed to parse %s' % s

        s = self.parse(name='Something', data='Something - Ep VIII')
        assert (s.season == 1 and s.episode == 8), 'failed to parse %s' % s

    def test_season_episode_of_total(self):
        """SeriesParser: season X YofZ"""
        s = self.parse(name='Something', data='Something Season 2 2of12')
        assert (s.season == 2 and s.episode == 2), 'failed to parse %s' % s

        s = self.parse(name='Something', data='Something Season 2, 2 of 12')
        assert (s.season == 2 and s.episode == 2), 'failed to parse %s' % s

    def test_episode_of_total(self):
        """SeriesParser: YofZ (assume season 1)"""
        s = self.parse(name='Something', data='Something 2of12')
        assert (s.season == 1 and s.episode == 2), 'failed to parse %s' % s

        s = self.parse(name='Something', data='Something 2 of 12')
        assert (s.season == 1 and s.episode == 2), 'failed to parse %s' % s

    def test_part(self):
        """SeriesParser: test parsing part numeral (assume season 1)"""
        s = self.parse(name='Test', data='Test.Pt.I.720p-FlexGet')
        assert (s.season == 1 and s.episode == 1), 'failed to parse %s' % s
        s = self.parse(name='Test', data='Test.Pt.VI.720p-FlexGet')
        assert (s.season == 1 and s.episode == 6), 'failed to parse %s' % s
        s = self.parse(name='Test', data='Test.Part.2.720p-FlexGet')
        assert (s.season == 1 and s.episode == 2), 'failed to parse %s' % s
        s = self.parse(name='Test', data='Test.Part3.720p-FlexGet')
        assert (s.season == 1 and s.episode == 3), 'failed to parse %s' % s
        s = self.parse(name='Test', data='Test.Season.3.Part.IV')
        assert (s.season == 3 and s.episode == 4), 'failed to parse %s' % s
        s = self.parse(name='Test', data='Test.Part.One')
        assert (s.season == 1 and s.episode == 1), 'failed to parse %s' % s

    def test_digits(self):
        """SeriesParser: digits (UID)"""
        s = self.parse(name='Something', data='Something 01 FlexGet')
        assert (s.id == 1), 'failed to parse %s' % s.data
        assert s.id_type == 'sequence'

        s = self.parse(name='Something', data='Something-121.H264.FlexGet')
        assert (s.id == 121), 'failed to parse %s' % s.data
        assert s.id_type == 'sequence'

        s = self.parse(name='Something', data='Something 1 AC3')
        assert (s.id == 1), 'failed to parse %s' % s.data
        assert s.id_type == 'sequence'

        s = self.parse(name='Something', data='[TheGroup] Something - 12 1280x720 x264-Hi10P')
        assert (s.id == 12), 'failed to parse %s' % s.data
        assert s.id_type == 'sequence'

    def test_quality(self):
        """SeriesParser: quality"""
        s = self.parse(name='Foo Bar', data='Foo.Bar.S01E01.720p.HDTV.x264-FlexGet')
        assert (s.season == 1 and s.episode == 1), 'failed to parse episodes from %s' % s.data
        assert (s.quality.name == '720p hdtv h264'), 'failed to parse quality from %s' % s.data

        s = self.parse(name='Test', data='Test.S01E01.720p-FlexGet')
        assert s.quality.name == '720p', 'failed to parse quality from %s' % s.data

        s = self.parse(name='30 Suck', data='30 Suck 4x4 [HDTV - FlexGet]')
        assert s.quality.name == 'hdtv', 'failed to parse quality %s' % s.data

        s = self.parse(name='ShowB', data='ShowB.S04E19.Name of Ep.720p.WEB-DL.DD5.1.H.264')
        assert s.quality.name == '720p webdl h264 dd5.1', 'failed to parse quality %s' % s.data

    def test_quality_parenthesis(self):
        """SeriesParser: quality in parenthesis"""
        s = self.parse(name='Foo Bar', data='Foo.Bar.S01E01.[720p].HDTV.x264-FlexGet')
        assert (s.season == 1 and s.episode == 1), 'failed to parse episodes from %s' % s.data
        assert (s.quality.name == '720p hdtv h264'), 'failed to parse quality from %s' % s.data

        s = self.parse(name='Foo Bar', data='Foo.Bar.S01E01.(720p).HDTV.x264-FlexGet')
        assert (s.season == 1 and s.episode == 1), 'failed to parse episodes from %s' % s.data
        assert (s.quality.name == '720p hdtv h264'), 'failed to parse quality from %s' % s.data

        s = self.parse(name='Foo Bar', data='[720p]Foo.Bar.S01E01.HDTV.x264-FlexGet')
        assert (s.season == 1 and s.episode == 1), 'failed to parse episodes from %s' % s.data
        assert (s.quality.name == '720p hdtv h264'), 'failed to parse quality from %s' % s.data

    def test_numeric_names(self):
        """SeriesParser: numeric names (24)"""
        s = self.parse(name='24', data='24.1x2-FlexGet')
        assert (s.season == 1 and s.episode == 2), 'failed to parse %s' % s.data

        s = self.parse(name='90120', data='90120.1x2-FlexGet')
        assert (s.season == 1 and s.episode == 2), 'failed to parse %s' % s.data

    def test_group_prefix(self):
        """SeriesParser: [group] before name"""
        s = self.parse(name='Foo Bar', data='[l.u.l.z] Foo Bar - 11 (H.264) [5235532D].mkv')
        assert (s.id == 11), 'failed to parse %s' % s.data

        s = self.parse(name='Foo Bar', data='[7.1.7.5] Foo Bar - 11 (H.264) [5235532D].mkv')
        assert (s.id == 11), 'failed to parse %s' % s.data

    def test_hd_prefix(self):
        """SeriesParser: HD 720p before name"""
        s = self.parse(name='Foo Bar', data='HD 720p: Foo Bar - 11 (H.264) [5235532D].mkv')
        assert (s.id == 11), 'failed to parse %s' % s.data
        assert (s.quality.name == '720p h264'), 'failed to pick up quality'

    def test_partially_numeric(self):
        """SeriesParser: partially numeric names"""
        s = self.parse(name='Foo 2009', data='Foo.2009.S02E04.HDTV.XviD-2HD[FlexGet]')
        assert (s.season == 2 and s.episode == 4), 'failed to parse %s' % s.data
        assert (s.quality.name == 'hdtv xvid'), 'failed to parse quality from %s' % s.data

    def test_ignore_seasonpacks(self):
        """SeriesParser: ignoring season packs"""
        #self.parse_invalid(name='The Foo', data='The.Foo.S04.1080p.FlexGet.5.1')
        self.parse_invalid(name='The Foo', data='The Foo S05 720p BluRay DTS x264-FlexGet')
        self.parse_invalid(name='The Foo', data='The Foo S05 720p BluRay DTS x264-FlexGet')
        self.parse_invalid(name='Something', data='Something S02 Pack 720p WEB-DL-FlexGet')
        self.parse_invalid(name='Something', data='Something S06 AC3-CRAPL3SS')
        self.parse_invalid(name='Something', data='Something SEASON 1 2010 540p BluRay QEBS AAC ANDROID IPAD MP4 FASM')
        self.parse_invalid(name='Something', data='Something.1x0.Complete.Season-FlexGet')
        self.parse_invalid(name='Something', data='Something.1xAll.Season.Complete-FlexGet')
        self.parse_invalid(name='Something', data='Something Seasons 1 & 2 - Complete')
        self.parse_invalid(name='Something', data='Something Seasons 4 Complete')
        self.parse_invalid(name='Something', data='Something Seasons 1 2 3 4')
        self.parse_invalid(name='Something', data='Something S6 E1-4')
        self.parse_invalid(name='Something', data='Something_Season_1_Full_Season_2_EP_1-7_HD')
        self.parse_invalid(name='Something', data='Something - Season 10 - FlexGet')
        self.parse_invalid(name='Something', data='Something_ DISC_1_OF_2 MANofKENT INVICTA RG')
        # Make sure no false positives
        assert self.parse(name='Something', data='Something S01E03 Full Throttle').valid


    def test_similar(self):
        s = self.parse(name='Foo Bar', data='Foo.Bar:Doppelganger.S02E04.HDTV.FlexGet', strict_name=True)
        assert not s.valid, 'should not have parser Foo.Bar:Doppelganger'
        s = self.parse(name='Foo Bar', data='Foo.Bar.Doppelganger.S02E04.HDTV.FlexGet', strict_name=True)
        assert not s.valid, 'should not have parser Foo.Bar.Doppelganger'

    def test_idiotic_numbering(self):
        """SeriesParser: idiotic 101, 102, 103, .. numbering"""
        s = SeriesParser(name='test', identified_by='ep')
        s.parse('Test.706.720p-FlexGet')
        assert s.season == 7, 'didn\'t pick up season'
        assert s.episode == 6, 'didn\'t pick up episode'

    def test_idiotic_numbering_with_zero(self):
        """SeriesParser: idiotic 0101, 0102, 0103, .. numbering"""
        s = SeriesParser(name='test', identified_by='ep')
        s.parse('Test.0706.720p-FlexGet')
        assert s.season == 7, 'season missing'
        assert s.episode == 6, 'episode missing'
        assert s.identifier == 'S07E06', 'identifier broken'

    def test_idiotic_invalid(self):
        """SeriesParser: idiotic confused by invalid"""
        s = SeriesParser(name='test', identified_by='ep')
        s.data = 'Test.Revealed.WS.PDTV.XviD-aAF.5190458.TPB.torrent'
        assert_raises(ParseWarning, s.parse)
        assert not s.season == 5, 'confused, got season'
        assert not s.season == 4, 'confused, got season'
        assert not s.episode == 19, 'confused, got episode'
        assert not s.episode == 58, 'confused, got episode'

    def test_zeroes(self):
        """SeriesParser: test zeroes as a season, episode"""

        for data in ['Test.S00E00-FlexGet', 'Test.S00E01-FlexGet', 'Test.S01E00-FlexGet']:
            s = self.parse(name='Test', data=data)
            id = s.identifier
            assert s.valid, 'parser not a valid for %s' % data
            assert isinstance(id, basestring), 'id is not a string for %s' % data
            assert isinstance(s.season, int), 'season is not a int for %s' % data
            assert isinstance(s.episode, int), 'season is not a int for %s' % data

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
        assert not s.valid, 'strict A failed'

        s = SeriesParser()
        s.strict_name = True
        s.name = 'Test AB'
        s.data = 'Test.AB.S01E02.720p-FlexGet'
        s.parse()
        assert s.valid, 'strict AB failed'

        s = SeriesParser()
        s.strict_name = True
        s.name = 'Red Tomato'
        s.data = 'Red Tomato (US) S01E02 720p-FlexGet'
        s.parse()
        assert not s.valid, 'Red Tomato (US) should not match Red Tomato in exact mode'

    def test_name_word_boundries(self):
        s = SeriesParser(name='test')
        s.parse('Test.S01E02.720p-FlexGet')
        assert s.valid, 'normal failed'
        # In non-exact mode these should match
        s.parse('Test.crap.S01E02.720p-FlexGet')
        assert s.valid, 'normal failed'
        s.parse('Test_crap.S01E02.720p-FlexGet')
        assert s.valid, 'underscore failed'
        # However if the title ends mid-word, it should not match
        s.parse('Testing.S01E02.720p-FlexGet')
        assert not s.valid, 'word border failed'

    def test_quality_as_ep(self):
        """SeriesParser: test that qualities are not picked as ep"""
        from flexget.utils import qualities
        for quality in qualities.all_components():
            s = SeriesParser(name='FooBar')
            s.data = 'FooBar %s XviD-FlexGet' % quality.name
            assert_raises(ParseWarning, s.parse)

    def test_sound_as_ep(self):
        """SeriesParser: test that sound infos are not picked as ep"""
        for sound in SeriesParser.sounds:
            s = SeriesParser()
            s.name = 'FooBar'
            s.data = 'FooBar %s XViD-FlexGet' % sound
            assert_raises(ParseWarning, s.parse)

    def test_ep_as_quality(self):
        """SeriesParser: test that eps are not picked as qualities"""
        from flexget.utils import qualities

        s = SeriesParser(name='FooBar')

        for quality1 in qualities.all_components():
            # Attempt to create an episode number out of quality
            mock_ep1 = filter(unicode.isdigit, quality1.name)
            if not mock_ep1:
                continue

            for quality2 in qualities.all_components():
                mock_ep2 = filter(unicode.isdigit, quality2.name)
                if not mock_ep2:
                    continue

                # 720i, 1080i, etc. are failing because
                # e.g the 720 in 720i can always be taken to mean 720p,
                # which is a higher priority quality.
                # Moreover, 1080 as an ep number is always failing because
                # sequence regexps support at most 3 digits at the moment.
                # Luckily, all of these cases are discarded by the following,
                # which also discards the failing cases when episode number
                # (e.g. 720) is greater or equal than quality number (e.g. 480p).
                # There's nothing that can be done with those failing cases with the
                # current
                # "grab leftmost occurrence of highest quality-like thing" algorithm.
                if int(mock_ep1) >= int(mock_ep2):
                    continue

                s.data = 'FooBar - %s %s-FlexGet' % (mock_ep1, quality2.name)
                s.parse()
                assert s.episode == int(mock_ep1), "confused episode %s with quality %s" % \
                                                  (mock_ep1, quality2.name)

                # Also test with reversed relative order of episode and quality
                s.data = '[%s] FooBar - %s [FlexGet]' % (quality2.name, mock_ep1)
                s.parse()
                assert s.episode == int(mock_ep1), "confused episode %s with quality %s" % \
                                                  (mock_ep1, quality2.name)

    def test_name_with_number(self):
        """SeriesParser: test number in a name"""
        s = SeriesParser()
        s.name = 'Storage 13'
        s.data = 'Storage 13 no ep number'
        assert_raises(ParseWarning, s.parse)

    def test_name_uncorrupted(self):
        """SeriesParser: test name doesn't get corrupted when cleaned"""
        s = self.parse(name='The New Adventures of Old Christine',
                       data='The.New.Adventures.of.Old.Christine.S05E16.HDTV.XviD-FlexGet')
        assert s.name == 'The New Adventures of Old Christine'
        assert s.season == 5
        assert s.episode == 16
        assert s.quality.name == 'hdtv xvid'

    def test_from_groups(self):
        """SeriesParser: test from groups"""
        s = SeriesParser()
        s.name = 'Test'
        s.data = 'Test.S01E01-Group'
        s.allow_groups = ['xxxx', 'group']
        s.parse()
        assert s.group == 'group', 'did not get group'

    def test_group_dashes(self):
        """SeriesParser: group name around extra dashes"""
        s = SeriesParser()
        s.name = 'Test'
        s.data = 'Test.S01E01-FooBar-Group'
        s.allow_groups = ['xxxx', 'group']
        s.parse()
        assert s.group == 'group', 'did not get group with extra dashes'

    def test_id_and_hash(self):
        """SeriesParser: Series with confusing hash"""
        s = self.parse(name='Something', data='Something 63 [560D3414]')
        assert (s.id == 63), 'failed to parse %s' % s.data

        s = self.parse(name='Something', data='Something 62 [293A8395]')
        assert (s.id == 62), 'failed to parse %s' % s.data

    def test_ticket_700(self):
        """SeriesParser: confusing name (#700)"""
        s = self.parse(name='Something', data='Something 9x02 - Episode 2')
        assert s.season == 9, 'failed to parse season'
        assert s.episode == 2, 'failed to parse episode'

    def test_date_id(self):
        """SeriesParser: Series with dates"""
        s = self.parse(name='Something', data='Something.2010.10.25')
        assert (s.identifier == '2010-10-25'), 'failed to parse %s' % s.data
        assert s.id_type == 'date'

        s = self.parse(name='Something', data='Something 2010-10-25')
        assert (s.identifier == '2010-10-25'), 'failed to parse %s' % s.data
        assert s.id_type == 'date'

        s = self.parse(name='Something', data='Something 10/25/2010')
        assert (s.identifier == '2010-10-25'), 'failed to parse %s' % s.data
        assert s.id_type == 'date'

        s = self.parse(name='Something', data='Something 25.10.2010')
        assert (s.identifier == '2010-10-25'), 'failed to parse %s' % s.data
        assert s.id_type == 'date'

        # February 1 is picked rather than January 2 because it is closer to now
        s = self.parse(name='Something', data='Something 1.2.11')
        assert s.identifier == '2011-02-01', 'failed to parse %s' % s.data
        assert s.id_type == 'date'

        # Future dates should not be considered dates
        s = self.parse(name='Something', data='Something 01.02.32')
        assert s.id_type != 'date'

        # Dates with parts used to be parsed as episodes.
        s = self.parse(name='Something', data='Something.2010.10.25, Part 2')
        assert (s.identifier == '2010-10-25'), 'failed to parse %s' % s.data
        assert s.id_type == 'date'

        # Text based dates
        s = self.parse(name='Something', data='Something (18th july 2013)')
        assert (s.identifier == '2013-07-18'), 'failed to parse %s' % s.data
        assert s.id_type == 'date'

        s = self.parse(name='Something', data='Something 2 mar 2013)')
        assert (s.identifier == '2013-03-02'), 'failed to parse %s' % s.data
        assert s.id_type == 'date'

        s = self.parse(name='Something', data='Something 1st february 1993)')
        assert (s.identifier == '1993-02-01'), 'failed to parse %s' % s.data
        assert s.id_type == 'date'

    def test_date_options(self):
        # By default we should pick the latest interpretation
        s = self.parse(name='Something', data='Something 01-02-03')
        assert (s.identifier == '2003-02-01'), 'failed to parse %s' % s.data

        # Test it still works with both options specified
        s = self.parse(name='Something', data='Something 01-02-03', date_yearfirst=False, date_dayfirst=True)
        assert (s.identifier == '2003-02-01'), 'failed to parse %s' % s.data

        # If we specify yearfirst yes it should force another interpretation
        s = self.parse(name='Something', data='Something 01-02-03', date_yearfirst=True)
        assert (s.identifier == '2001-02-03'), 'failed to parse %s' % s.data

        # If we specify dayfirst no it should force the third interpretation
        s = self.parse(name='Something', data='Something 01-02-03', date_dayfirst=False)
        assert (s.identifier == '2003-01-02'), 'failed to parse %s' % s.data

    def test_season_title_episode(self):
        """SeriesParser: Series with title between season and episode"""
        s = self.parse(name='Something', data='Something.S5.Drunk.Santa.Part1')
        assert s.season == 5, 'failed to parse season'
        assert s.episode == 1, 'failed to parse episode'

    def test_specials(self):
        """SeriesParser: Special episodes with no id"""
        s = self.parse(name='The Show', data='The Show 2005 A Christmas Carol 2010 Special 720p HDTV x264')
        assert s.valid, 'Special episode should be valid'

    def test_double_episodes(self):
        s = self.parse(name='Something', data='Something.S04E05-06')
        assert s.season == 4, 'failed to parse season'
        assert s.episode == 5, 'failed to parse episode'
        assert s.episodes == 2, 'failed to parse episode range'
        s = self.parse(name='Something', data='Something.S04E05-E06')
        assert s.season == 4, 'failed to parse season'
        assert s.episode == 5, 'failed to parse episode'
        assert s.episodes == 2, 'failed to parse episode range'
        s = self.parse(name='Something', data='Something.S04E05E06')
        assert s.season == 4, 'failed to parse season'
        assert s.episode == 5, 'failed to parse episode'
        assert s.episodes == 2, 'failed to parse episode range'
        s = self.parse(name='Something', data='Something.4x05-06')
        assert s.season == 4, 'failed to parse season'
        assert s.episode == 5, 'failed to parse episode'
        assert s.episodes == 2, 'failed to parse episode range'
        # Test that too large a range is not accepted
        s = self.parse(name='Something', data='Something.S04E05E09')
        assert s.valid == False, 'large episode range should not be valid'
        # Make sure regular identifier doesn't have end_episode
        s = self.parse(name='Something', data='Something.S04E05')
        assert s.episodes == 1, 'should not have detected end_episode'

    def test_and_replacement(self):
        titles = ['Alpha.&.Beta.S01E02.hdtv', 'alpha.and.beta.S01E02.hdtv', 'alpha&beta.S01E02.hdtv']
        for title in titles:
            s = self.parse(name='Alpha & Beta', data=title)
            assert s.valid
            s = self.parse(name='Alpha and Beta', data=title)
            assert s.valid
        # Test 'and' isn't replaced within a word
        s = self.parse(name='Sandy Dunes', data='S&y Dunes.S01E01.hdtv')
        assert not s.valid

    def test_unicode(self):
        s = self.parse(name=u'abc äää abc', data=u'abc.äää.abc.s01e02')
        assert s.season == 1
        assert s.episode == 2

    def test_parentheticals(self):
        s = SeriesParser('The Show (US)')
        # Make sure US is ok outside of parentheses
        s.parse('The.Show.US.S01E01')
        assert s.valid
        # Make sure US is ok inside parentheses
        s.parse('The Show (US) S01E01')
        assert s.valid
        # Make sure it works without US
        s.parse('The.Show.S01E01')
        assert s.valid
        # Make sure it doesn't work with a different country
        s.parse('The Show (UK) S01E01')
        assert not s.valid

    def test_id_regexps(self):
        s = SeriesParser('The Show', id_regexps=['(dog)?e(cat)?'])
        s.parse('The Show dogecat')
        assert s.valid
        assert s.id == 'dog-cat'
        s.parse('The Show doge')
        assert s.valid
        assert s.id == 'dog'
        s.parse('The Show ecat')
        assert s.valid
        assert s.id == 'cat'
        assert_raises(ParseWarning, s.parse, 'The Show e')

    def test_apostrophe(self):
        s = self.parse(name=u"FlexGet's show", data=u"FlexGet's show s01e01")
        assert s.valid
        s = self.parse(name=u"FlexGet's show", data=u"FlexGets show s01e01")
        assert s.valid
        s = self.parse(name=u"FlexGet's show", data=u"FlexGet s show s01e01")
        assert s.valid
        s = self.parse(name=u"FlexGet's show", data=u"FlexGet show s01e01")
        assert not s.valid
        # bad data with leftover escaping
        s = self.parse(name=u"FlexGet's show", data=u"FlexGet\\'s show s01e01")
        assert s.valid

    def test_alternate_names(self):
        s = SeriesParser('The Show', alternate_names=['Show', 'Completely Different'])
        s.parse('The Show S01E01')
        assert s.valid
        s.parse('Show S01E01')
        assert s.valid
        s.parse('Completely.Different.S01E01')
        assert s.valid
        s.parse('Not The Show S01E01')
        assert not s.valid

    def test_long_season(self):
        """SeriesParser: long season ID Ticket #2197"""
        s = self.parse(name='FlexGet', data='FlexGet.US.S2013E14.Title.Here.720p.HDTV.AAC5.1.x264-NOGRP')
        assert s.season == 2013
        assert s.episode == 14
        assert s.quality.name == '720p hdtv h264 aac'
        assert not s.proper, 'detected proper'

        s = self.parse(name='FlexGet', data='FlexGet.Series.2013.14.of.21.Title.Here.720p.HDTV.AAC5.1.x264-NOGRP')
        assert s.season == 2013
        assert s.episode == 14
        assert s.quality.name == '720p hdtv h264 aac'
        assert not s.proper, 'detected proper'
