import pytest

from flexget.components.parsing.parsers.parser_guessit import ParserGuessit
from flexget.components.parsing.parsers.parser_internal import ParserInternal


class TestSeriesParser:
    @pytest.fixture(
        scope='class', params=(ParserInternal, ParserGuessit), ids=['internal', 'guessit']
    )
    def parse(self, request):
        p = request.param()

        def parse(data, name=None, **kwargs):
            return p.parse_series(data, name=name, **kwargs)

        return parse

    @pytest.fixture(scope='class')
    def parse_invalid(self, parse):
        def parse_invalid(name, data, **kwargs):
            """Make sure either ParseWarning is raised, or return is invalid."""
            r = parse(data, name, **kwargs)
            assert not r.valid, f'{data} should not be valid'
            return r

        return parse_invalid

    @pytest.fixture(scope='class')
    def parse_valid(self, parse):
        def parse_valid(name, data, **kwargs):
            """Make sure return is valid."""
            r = parse(data, name, **kwargs)
            assert r.valid, f'{data} should be valid'
            return r

        return parse_valid

    def test_proper(self, parse):
        """SeriesParser: proper."""
        s = parse(name='Something Interesting', data='Something.Interesting.S01E02.Proper-FlexGet')
        assert s.season == 1
        assert s.episode == 2
        assert s.quality.name == 'unknown'
        assert s.proper, f'did not detect proper from {s.data}'
        s = parse(name='foobar', data='foobar 720p proper s01e01')
        assert s.proper, f'did not detect proper from {s.data}'

    def test_non_proper(self, parse):
        """SeriesParser: non-proper."""
        s = parse(name='Something Interesting', data='Something.Interesting.S01E02-FlexGet')
        assert s.season == 1
        assert s.episode == 2
        assert s.quality.name == 'unknown'
        assert not s.proper, 'detected proper'

    def test_anime_proper(self, parse):
        """SeriesParser: anime fansub style proper (13v2)."""
        s = parse(name='Anime', data='[aoeu] Anime 19v2 [23BA98]')
        assert s.identifier == 19
        assert s.proper_count == 1
        s = parse(name='Anime', data='Anime_-_19v3')
        assert s.identifier == 19
        assert s.proper_count == 2

    def test_basic(self, parse, parse_invalid):
        """SeriesParser: basic parsing."""
        parse_invalid(
            name='Something Interesting', data='The.Something.Interesting.S01E02-FlexGet'
        )

        s = parse(name='25', data='25.And.More.S01E02-FlexGet')
        assert s.valid, 'Fix the implementation, should be valid'
        assert s.identifier == 'S01E02', 'identifier broken'

    def test_confusing_date(self, parse):
        """SeriesParser: confusing (invalid) numbering scheme."""
        s = parse(name='Something', data='Something.2008x12.13-FlexGet')
        assert not s.episode, 'Should not have episode'
        assert s.id_type == 'date'
        assert s.identifier == '2008-12-13', 'invalid id'
        assert s.valid, 'should be valid'

    def test_unwanted_disc(self, parse_invalid):
        """SeriesParser: unwanted disc releases."""
        parse_invalid(name='Something', data='Something.S01D2.DVDR-FlexGet')

    def test_season_x_ep(self, parse):
        """SeriesParser: 01x02."""
        s = parse(name='Something', data='Something.01x02-FlexGet')
        assert s.season == 1, 'failed to parse 01x02'
        assert s.episode == 2, 'failed to parse 01x02'

        s = parse(name='Something', data='Something 1 x 2-FlexGet')
        assert s.season == 1, 'failed to parse 1 x 2'
        assert s.episode == 2, 'failed to parse 1 x 2'

        # Ticket #732
        s = parse(name='Something', data='Something - This is the Subtitle 14x9 [Group-Name]')
        assert s.season == 14, f'failed to parse {s.data}'
        assert s.episode == 9, f'failed to parse {s.data}'

    def test_ep_in_square_brackets(self, parse):
        """SeriesParser: [S01] [E02] NOT IMPLEMENTED."""
        s = parse(name='Something', data='Something [S01] [E02]')
        assert s.season == 1, f'failed to parse {s}'
        assert s.episode == 2, f'failed to parse {s}'

    def test_ep_in_parenthesis(self, parse):
        """SeriesParser: test ep in parenthesis."""
        s = parse(name='Something', data='Something (S01E02)')
        assert s.season == 1, f'failed to parse {s}'
        assert s.episode == 2, f'failed to parse {s}'

    def test_season_episode(self, parse):
        """SeriesParser: season X, episode Y."""
        s = parse(name='Something', data='Something - Season 3, Episode 2')
        assert s.season == 3, f'failed to parse {s}'
        assert s.episode == 2, f'failed to parse {s}'

        s = parse(name='Something', data='Something - Season2, Episode2')
        assert s.season == 2, f'failed to parse {s}'
        assert s.episode == 2, f'failed to parse {s}'

        s = parse(name='Something', data='Something - Season2 Episode2')
        assert s.season == 2, f'failed to parse {s}'
        assert s.episode == 2, f'failed to parse {s}'

    @pytest.mark.xfail(reason='Not supported in guessit, works for internal parser')
    def test_series_episode(self, parse):
        """SeriesParser: series X, episode Y."""
        s = parse(name='Something', data='Something - Series 2, Episode 2')
        assert s.season == 2, f'failed to parse {s}'
        assert s.episode == 2, f'failed to parse {s}'

        s = parse(name='Something', data='Something - Series3, Episode2')
        assert s.season == 3, f'failed to parse {s}'
        assert s.episode == 2, f'failed to parse {s}'

        s = parse(name='Something', data='Something - Series4 Episode2')
        assert s.season == 4, f'failed to parse {s}'
        assert s.episode == 2, f'failed to parse {s}'

    def test_episode(self, parse):
        """SeriesParser: episode X (assume season 1)."""
        s = parse(name='Something', data='Something - Episode2')
        assert s.season == 1, f'failed to parse {s}'
        assert s.episode == 2, f'failed to parse {s}'

        s = parse(name='Something', data='Something - Episode 2')
        assert s.season == 1, f'failed to parse {s}'
        assert s.episode == 2, f'failed to parse {s}'

        s = parse(name='Something', data='Something - Episode VIII')
        assert s.season == 1, f'failed to parse {s}'
        assert s.episode == 8, f'failed to parse {s}'

    def test_ep(self, parse):
        """SeriesParser: ep X (assume season 1)."""
        s = parse(name='Something', data='Something - Ep2')
        assert s.season == 1, f'failed to parse {s}'
        assert s.episode == 2, f'failed to parse {s}'

        s = parse(name='Something', data='Something - Ep 2')
        assert s.season == 1, f'failed to parse {s}'
        assert s.episode == 2, f'failed to parse {s}'

        s = parse(name='Something', data='Something - Ep VIII')
        assert s.season == 1, f'failed to parse {s}'
        assert s.episode == 8, f'failed to parse {s}'

        s = parse(name='Something', data='Something - E01')
        assert s.season == 1, f'failed to parse {s}'
        assert s.episode == 1, f'failed to parse {s}'

    def test_season_episode_of_total(self, parse):
        """SeriesParser: season X YofZ."""
        s = parse(name='Something', data='Something Season 2 2of12')
        assert s.season == 2, f'failed to parse {s}'
        assert s.episode == 2, f'failed to parse {s}'

        s = parse(name='Something', data='Something Season 2, 2 of 12')
        assert s.season == 2, f'failed to parse {s}'
        assert s.episode == 2, f'failed to parse {s}'

    def test_episode_of_total(self, parse):
        """SeriesParser: YofZ (assume season 1)."""
        s = parse(name='Something', data='Something 2of12')
        assert s.season == 1, f'failed to parse {s}'
        assert s.episode == 2, f'failed to parse {s}'

        s = parse(name='Something', data='Something 2 of 12')
        assert s.season == 1, f'failed to parse {s}'
        assert s.episode == 2, f'failed to parse {s}'

    def test_part(self, parse):
        """SeriesParser: test parsing part numeral (assume season 1)."""
        s = parse(name='Test', data='Test.Pt.I.720p-FlexGet')
        assert s.season == 1, f'failed to parse {s}'
        assert s.episode == 1, f'failed to parse {s}'
        s = parse(name='Test', data='Test.Pt.VI.720p-FlexGet')
        assert s.season == 1, f'failed to parse {s}'
        assert s.episode == 6, f'failed to parse {s}'
        s = parse(name='Test', data='Test.Part.2.720p-FlexGet')
        assert s.season == 1, f'failed to parse {s}'
        assert s.episode == 2, f'failed to parse {s}'
        assert s.identifier == 'S01E02'
        s = parse(name='Test', data='Test.Part3.720p-FlexGet')
        assert s.season == 1, f'failed to parse {s}'
        assert s.episode == 3, f'failed to parse {s}'
        s = parse(name='Test', data='Test.Season.3.Part.IV')
        assert s.season == 3, f'failed to parse {s}'
        assert s.episode == 4, f'failed to parse {s}'
        s = parse(name='Test', data='Test.Part.One')
        assert s.season == 1, f'failed to parse {s}'
        assert s.episode == 1, f'failed to parse {s}'

    def test_digits(self, parse):
        """SeriesParser: digits (UID)."""
        s = parse(name='Something', data='Something 01 FlexGet')
        assert s.id == 1, f'failed to parse {s.data}'
        assert s.id_type == 'sequence'

        s = parse(name='Something', data='Something-121.H264.FlexGet')
        assert s.id == 121, f'failed to parse {s.data}'
        assert s.id_type == 'sequence'

        s = parse(name='Something', data='Something 1 AC3')
        assert s.id == 1, f'failed to parse {s.data}'
        assert s.id_type == 'sequence'

        s = parse(name='Something', data='[TheGroup] Something - 12 1280x720 x264-Hi10P')
        assert s.id == 12, f'failed to parse {s.data}'
        assert s.id_type == 'sequence'

    def test_quality(self, parse):
        """SeriesParser: quality."""
        s = parse(name='Foo Bar', data='Foo.Bar.S01E01.720p.HDTV.x264-FlexGet')
        assert s.season == 1, f'failed to parse episodes from {s.data}'
        assert s.episode == 1, f'failed to parse episodes from {s.data}'
        assert s.quality.name == '720p hdtv h264', f'failed to parse quality from {s.data}'

        s = parse(name='Test', data='Test.S01E01.720p-FlexGet')
        assert s.quality.name == '720p', f'failed to parse quality from {s.data}'

        s = parse(name='30 Suck', data='30 Suck 4x4 [HDTV - FlexGet]')
        assert s.quality.name == 'hdtv', f'failed to parse quality {s.data}'

        s = parse(name='ShowB', data='ShowB.S04E19.Name of Ep.720p.WEB-DL.DD5.1.H.264')
        assert s.quality.name == '720p webdl h264 dd5.1', f'failed to parse quality {s.data}'

    def test_quality_parenthesis(self, parse):
        """SeriesParser: quality in parenthesis."""
        s = parse(name='Foo Bar', data='Foo.Bar.S01E01.[720p].HDTV.x264-FlexGet')
        assert s.season == 1, f'failed to parse episodes from {s.data}'
        assert s.episode == 1, f'failed to parse episodes from {s.data}'
        assert s.quality.name == '720p hdtv h264', f'failed to parse quality from {s.data}'

        s = parse(name='Foo Bar', data='Foo.Bar.S01E01.(720p).HDTV.x264-FlexGet')
        assert s.season == 1, f'failed to parse episodes from {s.data}'
        assert s.episode == 1, f'failed to parse episodes from {s.data}'
        assert s.quality.name == '720p hdtv h264', f'failed to parse quality from {s.data}'

        s = parse(name='Foo Bar', data='[720p]Foo.Bar.S01E01.HDTV.x264-FlexGet')
        assert s.season == 1, f'failed to parse episodes from {s.data}'
        assert s.episode == 1, f'failed to parse episodes from {s.data}'
        assert s.quality.name == '720p hdtv h264', f'failed to parse quality from {s.data}'

    def test_numeric_names(self, parse):
        """SeriesParser: numeric names (24)."""
        s = parse(name='24', data='24.1x2-FlexGet')
        assert s.season == 1, f'failed to parse {s.data}'
        assert s.episode == 2, f'failed to parse {s.data}'

        s = parse(name='90120', data='90120.1x2-FlexGet')
        assert s.season == 1, f'failed to parse {s.data}'
        assert s.episode == 2, f'failed to parse {s.data}'

    def test_group_prefix(self, parse):
        """SeriesParser: [group] before name."""
        s = parse(name='Foo Bar', data='[l.u.l.z] Foo Bar - 11 (H.264) [5235532D].mkv')
        assert s.id == 11, f'failed to parse {s.data}'

        s = parse(name='Foo Bar', data='[7.1.7.5] Foo Bar - 11 (H.264) [5235532D].mkv')
        assert s.id == 11, f'failed to parse {s.data}'

    def test_hd_prefix(self, parse):
        """SeriesParser: HD 720p before name."""
        s = parse(name='Foo Bar', data='HD 720p: Foo Bar - 11 (H.264) [5235532D].mkv')
        assert s.id == 11, f'failed to parse {s.data}'
        assert s.quality.name == '720p h264', 'failed to pick up quality'

    def test_partially_numeric(self, parse):
        """SeriesParser: partially numeric names."""
        s = parse(name='Foo 2009', data='Foo.2009.S02E04.HDTV.XviD-2HD[FlexGet]')
        assert s.season == 2, f'failed to parse {s.data}'
        assert s.episode == 4, f'failed to parse {s.data}'
        assert s.quality.name == 'hdtv xvid', f'failed to parse quality from {s.data}'

    def test_ignore_seasonpacks_by_default(self, parse, parse_valid, parse_invalid):
        """SeriesParser: ignoring season packs by default."""
        assert parse_valid(name='The Foo', data='The.Foo.S04.1080p.FlexGet.5.1').season_pack
        assert parse_valid(
            name='The Foo', data='The Foo S05 720p BluRay DTS x264-FlexGet'
        ).season_pack
        assert parse_valid(
            name='The Foo', data='The Foo S05 720p BluRay DTS x264-FlexGet'
        ).season_pack
        assert parse_valid(
            name='Something', data='Something S02 Pack 720p WEB-DL-FlexGet'
        ).season_pack
        assert parse_valid(name='Something', data='Something S06 AC3-CRAPL3SS').season_pack
        assert parse_valid(
            name='Something',
            data='Something SEASON 1 2010 540p BluRay QEBS AAC ANDROID IPAD MP4 FASM',
            identified_by='ep',
        ).season_pack
        assert parse_valid(
            name='Something', data='Something.1xAll.Season.Complete-FlexGet'
        ).season_pack
        assert parse_valid(name='Something', data='Something - Season 10 - FlexGet').season_pack

        # Multi season and multi episode are not allowed
        parse_invalid(name='Something', data='Something S6 E1-4')

        # Make sure no false positives
        parse_invalid(name='Something', data='Something.1x0.Complete.Season-FlexGet')
        parse_invalid(name='Something', data='Something_Season_1_Full_Season_2_EP_1-7_HD')
        parse_invalid(name='Something', data='Something_ S01D2 MANofKENT INVICTA RG')

    def test_allow_seasonpacks_by_ep(self, parse, parse_valid, parse_invalid):
        """SeriesParser: allowing season packs by ep."""
        assert parse_valid(
            name='The Foo', data='The.Foo.S04.1080p.FlexGet.5.1', identified_by='ep'
        ).season_pack
        assert parse_valid(
            name='The Foo', data='The Foo S05 720p BluRay DTS x264-FlexGet', identified_by='ep'
        ).season_pack
        assert parse_valid(
            name='The Foo', data='The Foo S05 720p BluRay DTS x264-FlexGet', identified_by='ep'
        ).season_pack
        assert parse_valid(
            name='Something', data='Something S02 Pack 720p WEB-DL-FlexGet', identified_by='ep'
        ).season_pack
        assert parse_valid(
            name='Something', data='Something S06 AC3-CRAPL3SS', identified_by='ep'
        ).season_pack
        assert parse_valid(
            name='Something',
            data='Something SEASON 1 2010 540p BluRay QEBS AAC ANDROID IPAD MP4 FASM',
            identified_by='ep',
        ).season_pack
        assert parse_valid(
            name='Something', data='Something.1xAll.Season.Complete-FlexGet', identified_by='ep'
        ).season_pack
        assert parse_valid(
            name='Something', data='Something - Season 10 - FlexGet', identified_by='ep'
        ).season_pack

        # Season pack by episode group are not allowed
        parse_invalid(name='Something', data='Something S6 E1-4', identified_by='ep')

        # Make sure no false positives
        parse_invalid(
            name='Something', data='Something.1x0.Complete.Season-FlexGet', identified_by='ep'
        )
        parse_invalid(
            name='Something', data='Something_Season_1_Full_Season_2_EP_1-7_HD', identified_by='ep'
        )
        parse_invalid(
            name='Something', data='Something_ S01D2 MANofKENT INVICTA RG', identified_by='ep'
        )

    @pytest.mark.parametrize(
        "parse",
        [(ParserGuessit)],
        ids=["guessit"],
        indirect=["parse"],
    )
    def test_ignore_multi_seasonpacks(self, parse, parse_valid, parse_invalid):
        """SeriesParser: ignore multi season and multi episode (only supported by guessit)."""
        parse_invalid(
            name='Something', data='Something Seasons 1 & 2 - Complete', identified_by='ep'
        )
        parse_invalid(name='Something', data='Something Seasons 1 2 3 4', identified_by='ep')
        parse_invalid(name='Something', data='Something S01-03 Full Throttle', identified_by='ep')
        parse_invalid(name='Something', data='Something S6 E1-4', identified_by='ep')

        # Make sure no false positives
        assert parse_valid(
            name='The Foo', data='The.Foo.S04.1080p.FlexGet.5.1', identified_by='ep'
        ).season_pack
        assert parse_valid(
            name='Something', data='Something Seasons 4 Complete', identified_by='ep'
        ).season_pack

    def test_similar(self, parse):
        s = parse(
            name='Foo Bar', data='Foo.Bar:Doppelganger.S02E04.HDTV.FlexGet', strict_name=True
        )
        assert not s.valid, 'should not have parser Foo.Bar:Doppelganger'
        s = parse(
            name='Foo Bar', data='Foo.Bar.Doppelganger.S02E04.HDTV.FlexGet', strict_name=True
        )
        assert not s.valid, 'should not have parser Foo.Bar.Doppelganger'

    def test_idiotic_numbering(self, parse):
        """SeriesParser: idiotic 101, 102, 103, .. numbering."""
        s = parse('Test.706.720p-FlexGet', name='test', identified_by='ep')
        assert s.season == 7, 'didn\'t pick up season'
        assert s.episode == 6, 'didn\'t pick up episode'

    def test_idiotic_numbering_with_zero(self, parse):
        """SeriesParser: idiotic 0101, 0102, 0103, .. numbering."""
        s = parse('Test.0706.720p-FlexGet', name='test', identified_by='ep')
        assert s.season == 7, 'season missing'
        assert s.episode == 6, 'episode missing'
        assert s.identifier == 'S07E06', 'identifier broken'

    def test_idiotic_invalid(self, parse):
        """SeriesParser: idiotic confused by invalid."""
        s = parse(
            'Test.Revealed.WS.PDTV.XviD-aAF.5190458.TPB.torrent', name='test', identified_by='ep'
        )
        # assert_raises(ParseWarning, s.parse)
        assert s.season != 5, 'confused, got season'
        assert s.season != 4, 'confused, got season'
        assert s.episode != 19, 'confused, got episode'
        assert s.episode != 58, 'confused, got episode'

    def test_zeroes(self, parse):
        """SeriesParser: test zeroes as a season, episode."""
        for data in ['Test.S00E00-FlexGet', 'Test.S00E01-FlexGet', 'Test.S01E00-FlexGet']:
            s = parse(name='Test', data=data)
            id = s.identifier
            assert s.valid, f'parser not a valid for {data}'
            assert isinstance(id, str), f'id is not a string for {data}'
            assert isinstance(s.season, int), f'season is not a int for {data}'
            assert isinstance(s.episode, int), f'season is not a int for {data}'

    def test_exact_name(self, parse):
        """SeriesParser: test exact/strict name parsing."""
        s = parse('Test.Foobar.S01E02.720p-FlexGet', name='test')
        assert s.valid, 'normal failed'

        s = parse('Test.A.S01E02.720p-FlexGet', name='test', strict_name=True)
        assert not s.valid, 'strict A failed'

        s = parse('Test.AB.S01E02.720p-FlexGet', name='Test AB', strict_name=True)
        assert s.valid, 'strict AB failed'

        s = parse('Red Tomato (US) S01E02 720p-FlexGet', name='Red Tomato', strict_name=True)
        assert not s.valid, 'Red Tomato (US) should not match Red Tomato in exact mode'

    def test_name_word_boundries(self, parse):
        name = 'test'
        s = parse('Test.S01E02.720p-FlexGet', name=name)
        assert s.valid, 'normal failed'
        # In non-exact mode these should match
        s = parse('Test.crap.S01E02.720p-FlexGet', name=name)
        assert s.valid, 'normal failed'
        s = parse('Test_crap.S01E02.720p-FlexGet', name=name)
        assert s.valid, 'underscore failed'
        # However if the title ends mid-word, it should not match
        s = parse('Testing.S01E02.720p-FlexGet', name=name)
        assert not s.valid, 'word border failed'

    def test_quality_as_ep(self, parse):
        """SeriesParser: test that qualities are not picked as ep."""
        from flexget.utils import qualities

        for quality in qualities.all_components():
            parse(f'FooBar {quality.name} XviD-FlexGet', name='FooBar')

    def test_sound_as_ep(self, parse):
        """SeriesParser: test that sound infos are not picked as ep."""
        sounds = ['AC3', 'DD5.1', 'DTS']
        for sound in sounds:
            parse(data=f'FooBar {sound} XViD-FlexGet', name='FooBar')

    @pytest.mark.xfail(reason='Bug in guessit, works for internal parser')
    def test_ep_as_quality(self, parse):
        """SeriesParser: test that eps are not picked as qualities."""
        from flexget.utils import qualities

        for quality1 in qualities.all_components():
            # Attempt to create an episode number out of quality
            mock_ep1 = ''.join(list(filter(str.isdigit, quality1.name)))
            if not mock_ep1:
                continue

            for quality2 in qualities.all_components():
                mock_ep2 = ''.join(list(filter(str.isdigit, quality2.name)))
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
                if int(mock_ep1) >= int(mock_ep2) or int(mock_ep2) > 999:
                    continue

                s = parse(f'FooBar - {mock_ep1} {quality2.name}-FlexGet', name='FooBar')
                assert s.episode == int(mock_ep1), (
                    f"confused episode {mock_ep1} with quality {quality2.name}"
                )

                # Also test with reversed relative order of episode and quality
                s = parse(f'[{quality2.name}] FooBar - {mock_ep1} [FlexGet]', name='FooBar')
                assert s.episode == int(mock_ep1), (
                    f"confused episode {mock_ep1} with quality {quality2.name}"
                )

    def test_name_with_number(self, parse):
        """SeriesParser: test number in a name."""
        parse('Storage 13 no ep number', name='Storage 13')

    def test_name_uncorrupted(self, parse):
        """SeriesParser: test name doesn't get corrupted when cleaned."""
        s = parse(
            name='The New Adventures of Old Christine',
            data='The.New.Adventures.of.Old.Christine.S05E16.HDTV.XviD-FlexGet',
        )
        assert s.name == 'The New Adventures of Old Christine'
        assert s.season == 5
        assert s.episode == 16
        assert s.quality.name == 'hdtv xvid'

    def test_from_groups(self, parse):
        """SeriesParser: test from groups."""
        s = parse('Test.S01E01-Group', name='Test', allow_groups=['xxxx', 'group'])
        assert s.group.lower() == 'group', 'did not get group'

    def test_group_dashes(self, parse):
        """SeriesParser: group name around extra dashes."""
        s = parse('Test.S01E01-FooBar-Group', name='Test', allow_groups=['xxxx', 'group'])
        assert s.group.lower() == 'group', 'did not get group with extra dashes'

    def test_id_and_hash(self, parse):
        """SeriesParser: Series with confusing hash."""
        s = parse(name='Something', data='Something 63 [560D3414]')
        assert s.id == 63, f'failed to parse {s.data}'

        s = parse(name='Something', data='Something 62 [293A8395]')
        assert s.id == 62, f'failed to parse {s.data}'

    def test_ticket_700(self, parse):
        """SeriesParser: confusing name (#700)."""
        s = parse(name='Something', data='Something 9x02 - Episode 2')
        assert s.season == 9, 'failed to parse season'
        assert s.episode == 2, 'failed to parse episode'

    def test_date_id(self, parse):
        """SeriesParser: Series with dates."""
        s = parse(name='Something', data='Something.2010.10.25')
        assert s.identifier == '2010-10-25', f'failed to parse {s.data}'
        assert s.id_type == 'date'

        s = parse(name='Something', data='Something 2010-10-25')
        assert s.identifier == '2010-10-25', f'failed to parse {s.data}'
        assert s.id_type == 'date'

        s = parse(name='Something', data='Something 10/25/2010')
        assert s.identifier == '2010-10-25', f'failed to parse {s.data}'
        assert s.id_type == 'date'

        s = parse(name='Something', data='Something 25.10.2010')
        assert s.identifier == '2010-10-25', f'failed to parse {s.data}'
        assert s.id_type == 'date'

        # February 1 is picked rather than January 2 because it is closer to now
        s = parse(name='Something', data='Something 1.2.11')
        assert s.identifier == '2011-02-01', f'failed to parse {s.data}'
        assert s.id_type == 'date'

        # Future dates should not be considered dates
        s = parse(name='Something', data='Something 01.02.32')
        assert s.id_type != 'date'

        # Dates with parts used to be parsed as episodes.
        s = parse(name='Something', data='Something.2010.10.25, Part 2')
        assert s.identifier == '2010-10-25', f'failed to parse {s.data}'
        assert s.id_type == 'date'

        # Text based dates
        s = parse(name='Something', data='Something (18th july 2013)')
        assert s.identifier == '2013-07-18', f'failed to parse {s.data}'
        assert s.id_type == 'date'

        s = parse(name='Something', data='Something 2 mar 2013)')
        assert s.identifier == '2013-03-02', f'failed to parse {s.data}'
        assert s.id_type == 'date'

        s = parse(name='Something', data='Something 1st february 1993)')
        assert s.identifier == '1993-02-01', f'failed to parse {s.data}'
        assert s.id_type == 'date'

    def test_date_options(self, parse):
        # By default we should pick the latest interpretation
        s = parse(name='Something', data='Something 01-02-03')
        assert s.identifier == '2003-02-01', f'failed to parse {s.data}'

        # Test it still works with both options specified
        s = parse(
            name='Something', data='Something 01-02-03', date_yearfirst=False, date_dayfirst=True
        )
        assert s.identifier == '2003-02-01', f'failed to parse {s.data}'

        # If we specify yearfirst yes it should force another interpretation
        s = parse(name='Something', data='Something 01-02-03', date_yearfirst=True)
        assert s.identifier == '2001-03-02', f'failed to parse {s.data}'

        # If we specify dayfirst no it should force the third interpretation
        s = parse(name='Something', data='Something 01-02-03', date_dayfirst=False)
        assert s.identifier == '2003-01-02', f'failed to parse {s.data}'

    def test_season_title_episode(self, parse):
        """SeriesParser: Series with title between season and episode."""
        s = parse(name='Something', data='Something.S5.Drunk.Santa.Part1')
        assert s.season == 5, 'failed to parse season'
        assert s.episode == 1, 'failed to parse episode'

    def test_specials(self, parse):
        """SeriesParser: Special episodes with no id."""
        s = parse(
            name='The Show', data='The Show 2005 A Christmas Carol 2010 Special 720p HDTV x264'
        )
        assert s.valid, 'Special episode should be valid'

    def test_double_episodes(self, parse):
        s = parse(name='Something', data='Something.S04E05-06')
        assert s.season == 4, 'failed to parse season'
        assert s.episode == 5, 'failed to parse episode'
        assert s.episodes == 2, 'failed to parse episode range'
        s = parse(name='Something', data='Something.S04E05-E06')
        assert s.season == 4, 'failed to parse season'
        assert s.episode == 5, 'failed to parse episode'
        assert s.episodes == 2, 'failed to parse episode range'
        s = parse(name='Something', data='Something.S04E05E06')
        assert s.season == 4, 'failed to parse season'
        assert s.episode == 5, 'failed to parse episode'
        assert s.episodes == 2, 'failed to parse episode range'
        s = parse(name='Something', data='Something.4x05-06')
        assert s.season == 4, 'failed to parse season'
        assert s.episode == 5, 'failed to parse episode'
        assert s.episodes == 2, 'failed to parse episode range'
        # Test that too large a range is not accepted
        s = parse(name='Something', data='Something.S04E05-09')
        assert not s.valid, 'large episode range should not be valid'
        # Make sure regular identifier doesn't have end_episode
        s = parse(name='Something', data='Something.S04E05')
        assert s.episodes == 1, 'should not have detected end_episode'

    def test_and_replacement(self, parse):
        titles = [
            'Alpha.&.Beta.S01E02.hdtv',
            'alpha.and.beta.S01E02.hdtv',
            'alpha&beta.S01E02.hdtv',
        ]
        for title in titles:
            s = parse(name='Alpha & Beta', data=title)
            assert s.valid
            s = parse(name='Alpha and Beta', data=title)
            assert s.valid
        # Test 'and' isn't replaced within a word
        s = parse(name='Sandy Dunes', data='S&y Dunes.S01E01.hdtv')
        assert not s.valid

    def test_unicode(self, parse):
        s = parse(name='abc äää abc', data='abc.äää.abc.s01e02')
        assert s.season == 1
        assert s.episode == 2

    def test_parentheticals(self, parse):
        s = parse('The Show (US)', name="The Show (US)")
        # Make sure US is ok outside of parentheses
        s = parse('The.Show.US.S01E01', name="The Show (US)")
        assert s.valid
        # Make sure US is ok inside parentheses
        s = parse('The Show (US) S01E01', name="The Show (US)")
        assert s.valid
        # Make sure it works without US
        s = parse('The.Show.S01E01', name="The Show (US)")
        assert s.valid
        # Make sure it doesn't work with a different country
        s = parse('The Show (UK) S01E01', name="The Show (US)")
        assert not s.valid

    def test_id_regexps(self, parse):
        id_regexps = ['(dog)?e(cat)?']
        s = parse('The Show dogecat', name='The Show', id_regexps=id_regexps)
        assert s.valid
        assert s.id == 'dog-cat'
        s = parse('The Show doge', name='The Show', id_regexps=id_regexps)
        assert s.valid
        assert s.id == 'dog'
        s = parse('The Show ecat', name='The Show', id_regexps=id_regexps)
        assert s.valid
        assert s.id == 'cat'
        # assert_raises(ParseWarning, s.parse, 'The Show e')

    def test_apostrophe(self, parse):
        s = parse(name="FlexGet's show", data="FlexGet's show s01e01")
        assert s.valid
        s = parse(name="FlexGet's show", data="FlexGets show s01e01")
        assert s.valid
        s = parse(name="FlexGet's show", data="FlexGet s show s01e01")
        assert s.valid
        s = parse(name="FlexGet's show", data="FlexGet show s01e01")
        assert not s.valid
        # bad data with leftover escaping
        s = parse(name="FlexGet's show", data="FlexGet\\'s show s01e01")
        assert s.valid

    def test_alternate_names(self, parse):
        name = 'The Show'
        alternate_names = ['Show', 'Completely Different']
        s = parse('The Show S01E01', name=name, alternate_names=alternate_names)
        assert s.valid
        s = parse('Show S01E01', name=name, alternate_names=alternate_names)
        assert s.valid
        s = parse('Completely.Different.S01E01', name=name, alternate_names=alternate_names)
        assert s.valid
        s = parse('Not The Show S01E01', name=name, alternate_names=alternate_names)
        assert not s.valid

    def test_long_season(self, parse):
        """SeriesParser: long season ID Ticket #2197."""
        s = parse(
            name='FlexGet', data='FlexGet.US.S2013E14.Title.Here.720p.HDTV.AAC5.1.x264-NOGRP'
        )
        assert s.season == 2013
        assert s.episode == 14
        assert s.quality.name == '720p hdtv h264 aac'
        assert not s.proper, 'detected proper'

        s = parse(
            name='FlexGet',
            data='FlexGet.Series.2013.14.of.21.Title.Here.720p.HDTV.AAC5.1.x264-NOGRP',
        )
        assert s.season == 2013
        assert s.episode == 14
        assert s.quality.name == '720p hdtv h264 aac'
        assert not s.proper, 'detected proper'

    def test_episode_with_season_pack_match_is_not_season_pack(self, parse):
        r"""SeriesParser: Github issue #1986, s\d{1} parses as invalid season."""
        s = parse(name='The Show', data='The.Show.S01E01.eps3.0.some.title.720p.x264-NOGRP')
        assert s.valid
        assert not s.season_pack
        assert s.season == 1
        assert s.episode == 1
