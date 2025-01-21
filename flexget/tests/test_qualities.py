import pytest
from jinja2 import Template

from flexget.components.parsing.parsers.parser_guessit import ParserGuessit
from flexget.components.parsing.parsers.parser_internal import ParserInternal
from flexget.utils.qualities import Quality


class TestQualityModule:
    def test_get(self):
        assert not Quality(), 'unknown quality is not false'
        assert Quality('foobar') == Quality(), 'unknown not returned'

    def test_common_name(self):
        for test_val in ('720p', '1280x720'):
            got_val = Quality(test_val).name
            assert got_val == '720p', got_val


class TestQualityParser:
    @pytest.fixture(
        scope='class', params=['internal', 'guessit'], ids=['internal', 'guessit'], autouse=True
    )
    def parser(self, request):
        if request.param == 'internal':
            return ParserInternal
        if request.param == 'guessit':
            return ParserGuessit
        return None

    @pytest.mark.parametrize(
        "test_quality",
        [
            ('Test.File.dvdscr', 'dvdscr'),
            ('Test.File 1080p.web.vp9', '1080p webdl vp9'),
            ('Test.File 1080p.web', '1080p webdl'),
            ('Test.File.2160p.web', '2160p webdl'),
            ('Test.File.1080.web-random', '1080p webdl'),
            ('Test.File.1080.webrandom', '1080p'),
            ('Test.File 1080p.web-dl', '1080p webdl'),
            ('Test.File.web-dl.1080p', '1080p webdl'),
            ('Test.File.WebHD.720p', '720p webdl'),
            ('Test.File.720p.bluray', '720p bluray'),
            ('Test.File.720hd.bluray', '720p bluray'),
            ('Test.File.1080p.bluray', '1080p bluray'),
            ('Test.File.2160p.bluray', '2160p bluray'),
            ('Test.File.1080p.cam', '1080p cam'),
            ('A Movie 2011 TS 576P XviD-DTRG', '576p ts xvid'),
            ('Test.File.720p.bluray.r5', '720p r5'),
            ('Test.File.1080p.bluray.rc', '1080p r5'),
            # 10bit
            ('Test.File.480p.10bit', '480p 10bit'),
            ('Test.File.720p.10bit', '720p 10bit'),
            ('Test.File.720p.bluray.10bit', '720p bluray 10bit'),
            ('Test.File.1080p.10bit', '1080p 10bit'),
            ('Test.File.1080p.bluray.10bit', '1080p bluray 10bit'),
            ('Test.File.720p.web', '720p webdl'),
            ('Test.File.720p.webdl', '720p webdl'),
            ('Test.File.1280x720_web dl', '720p webdl'),
            ('Test.File.720p.h264.web.dl', '720p webdl h264'),
            ('Test.File.1080p.webhd.x264', '1080p webdl h264'),
            ('Test.File.REPACK.1080p.WEBRip.DDP5.1.x264', '1080p webrip h264 dd+5.1'),
            ('Test.File.480.hdtv.x265', '480p hdtv h265'),
            ('Test.File.web', 'webdl'),
            ('Test.File.web-dl', 'webdl'),
            ('Test.File.720P', '720p'),
            ('Test.File.1920x1080', '1080p'),
            ('Test.File.3840x2160', '2160p'),
            ('Test.File.1080i', '1080i'),
            ('Test File blurayrip', 'bluray'),
            ('Test.File.br-rip', 'bluray'),
            ('Test.File.720px', '720p'),
            ('Test.File.720p50', '720p'),
            ('Test.File.720p60', '720p'),
            ('Test.File.dvd.rip', 'dvdrip'),
            ('Test.File.dvd.rip.r5', 'r5'),
            ('Test.File.[576p][00112233].mkv', '576p'),
            ('Test.TS.FooBar', 'ts'),
            ('Test.File.360p.avi', '360p'),
            ('Test.File.[360p].mkv', '360p'),
            ('Test.File.368.avi', '368p'),
            ('Test.File.720p.hdtv.avi', '720p hdtv'),
            ('Test.File.1080p.hdtv.avi', '1080p hdtv'),
            ('Test.File.720p.preair.avi', '720p preair'),
            # ('Test.File.ts.dvdrip.avi', 'ts'), This should no exists. Having Telesync and DVDRip is a non-sense.
            ('Test.File.HDTS.blah', 'ts'),
            # ('Test.File.HDCAM.bluray.lie', 'cam'), This should no exists. Having Cam and Bluray is a non-sense.
            # Test qualities as part of words. #1593
            ('Tsar.File.720p', '720p'),
            ('Camera.1080p', '1080p'),
            # Some audio formats
            ('Test.File.DTSHDMA', 'dtshd'),
            ('Test.File.DTSHD.MA', 'dtshd'),
            ('Test.File.DTS.HDMA', 'dtshd'),
            ('Test.File.dts.hd.ma', 'dtshd'),
            ('Test.File.DTS.HD', 'dtshd'),
            ('Test.File.DTSHD', 'dtshd'),
            ('Test.File.DTS', 'dts'),
            ('Test.File.truehd', 'truehd'),
            ('Test.File.truehd7.1', 'truehd'),
            ('Test.File.truehd.7.1', 'truehd'),
            ('Test.File.DTSHDMA', 'dtshd'),
            ('Test.File.DTSHDMA5.1', 'dtshd'),
            ('Test.File.DD2.0', 'dd5.1', False),
            ('Test.File.AC35.1', 'ac3', False),
        ],
    )
    def test_quality_failures(self, parser, test_quality):
        # Kind of a hack to get around the awful limitations of Guessit without creating extra tests
        guessit = test_quality[2] if len(test_quality) > 2 else True
        if not guessit and parser.__name__ == 'ParserGuessit':
            return
        quality = parser().parse_movie(test_quality[0]).quality
        assert str(quality) == test_quality[1], (
            f'`{test_quality[0]}` quality should be `{test_quality[1]}` not `{quality}`'
        )


class TestQualityInternalParser:
    @pytest.mark.parametrize(
        "test_quality",
        [
            ('Test.File.DD+5.1', 'dd+5.1'),
            ('Test.File.DDP5.1', 'dd+5.1'),
            ('Test.File.DDP7.1', 'dd+5.1'),
            ('Test.File.DD5.1', 'dd5.1'),
            ('Test.File.DD4.0', 'dd5.1'),
            ('Test.File.DD2.1', 'dd5.1'),
            ('Test.File.FLAC1.0', 'flac'),
        ],
    )
    def test_quality_failures(self, test_quality):
        quality = ParserInternal().parse_movie(test_quality[0]).quality
        assert str(quality) == test_quality[1], (
            f'`{test_quality[0]}` quality should be `{test_quality[1]}` not `{quality}`'
        )


class TestFilterQuality:
    _config = """
        templates:
          global:
            parsing:
              series: {{parser}}
              movie: {{parser}}
            mock:
              - {title: 'Smoke.1280x720'}
              - {title: 'Smoke.HDTV'}
              - {title: 'Smoke.cam'}
              - {title: 'Smoke.HR'}
            accept_all: yes
        tasks:
          qual:
            quality:
              - hdtv
              - 720p
          min:
            quality: HR+
          max:
            quality: "<=cam <HR"
          min_max:
            quality: HR-720i
          quality_str:
            template: no_global
            mock:
              - {title: 'Test S01E01 HDTV 1080p', quality: 'hdtv 1080p dd+5.1'}
            accept_all: yes
    """

    @pytest.fixture(scope='class', params=['internal', 'guessit'], ids=['internal', 'guessit'])
    def config(self, request):
        """Override and parametrize default config fixture."""
        return Template(self._config).render({'parser': request.param})

    def test_quality(self, execute_task):
        task = execute_task('qual')
        entry = task.find_entry('rejected', title='Smoke.cam')
        assert entry, 'Smoke.cam should have been rejected'

        entry = task.find_entry(title='Smoke.1280x720')
        assert entry, 'entry not found?'
        assert entry in task.accepted, '720p should be accepted'
        assert len(task.rejected) == 2, 'wrong number of entries rejected'
        assert len(task.accepted) == 2, 'wrong number of entries accepted'

    def test_min(self, execute_task):
        task = execute_task('min')
        entry = task.find_entry('rejected', title='Smoke.HDTV')
        assert entry, 'Smoke.HDTV should have been rejected'

        entry = task.find_entry(title='Smoke.1280x720')
        assert entry, 'entry not found?'
        assert entry in task.accepted, '720p should be accepted'
        assert len(task.rejected) == 2, 'wrong number of entries rejected'
        assert len(task.accepted) == 2, 'wrong number of entries accepted'

    def test_max(self, execute_task):
        task = execute_task('max')
        entry = task.find_entry('rejected', title='Smoke.1280x720')
        assert entry, 'Smoke.1280x720 should have been rejected'

        entry = task.find_entry(title='Smoke.cam')
        assert entry, 'entry not found?'
        assert entry in task.accepted, 'cam should be accepted'
        assert len(task.rejected) == 3, 'wrong number of entries rejected'
        assert len(task.accepted) == 1, 'wrong number of entries accepted'

    def test_min_max(self, execute_task):
        task = execute_task('min_max')
        entry = task.find_entry('rejected', title='Smoke.1280x720')
        assert entry, 'Smoke.1280x720 should have been rejected'

        entry = task.find_entry(title='Smoke.HR')
        assert entry, 'entry not found?'
        assert entry in task.accepted, 'HR should be accepted'
        assert len(task.rejected) == 3, 'wrong number of entries rejected'
        assert len(task.accepted) == 1, 'wrong number of entries accepted'

    def test_quality_string(self, execute_task):
        task = execute_task('quality_str')
        entry = task.find_entry('accepted', title='Test S01E01 HDTV 1080p')
        assert isinstance(entry['quality'], Quality), (
            'Wrong quality type, should be Quality not str'
        )
        assert str(entry['quality']) == '1080p hdtv dd+5.1'


class TestQualityAudio:
    config = """
        tasks:
          test_dd_audio_channels:
            quality: "dd+5.1"
            mock:
              - {title: 'My Show S01E05 720p HDTV DD+7.1'}
              - {title: 'My Show S01E05 720p HDTV DD+5.0'}
          test_dd_audio_min:
            quality: ">dd5.1"
            mock:
              - {title: 'My Show S01E05 720p HDTV DD5.1'}
              - {title: 'My Show S01E05 720p HDTV DD+2.0'}
          test_dd_audio_max:
            quality: "<=dd5.1"
            mock:
              - {title: 'My Show S01E05 720p HDTV DD5.1'}
              - {title: 'My Show S01E05 720p HDTV DD+5.1'}
              - {title: 'My Show S01E05 720p HDTV DD+7.1'}
    """

    def test_dd_audio_channels(self, execute_task):
        task = execute_task('test_dd_audio_channels')
        entry = task.find_entry('undecided', title='My Show S01E05 720p HDTV DD+7.1')
        assert entry, 'Entry "My Show S01E05 720p HDTV DD+7.1" should not have been rejected'
        assert entry['quality'].audio == 'dd+5.1', (
            'audio "dd+7.1" should have been parsed as dd+5.1'
        )

        entry = task.find_entry('undecided', title='My Show S01E05 720p HDTV DD+5.0')
        assert entry['quality'].audio == 'dd+5.1', (
            'audio "dd+5.0" should have been parsed as dd+5.1'
        )

    def test_dd_audio_min(self, execute_task):
        task = execute_task('test_dd_audio_min')
        assert len(task.rejected) == 1, 'should have rejected one'
        entry = task.find_entry('undecided', title='My Show S01E05 720p HDTV DD+2.0')
        assert entry, 'Entry "My Show S01E05 720p HDTV DD+2.0" should not have been rejected'
        assert entry['quality'].audio == 'dd+5.1', 'audio should have been parsed as dd+5.1'

    def test_dd_audio_max(self, execute_task):
        task = execute_task('test_dd_audio_max')
        assert len(task.rejected) == 2, 'should have rejected two'
        entry = task.find_entry('undecided', title='My Show S01E05 720p HDTV DD5.1')
        assert entry, 'Entry "My Show S01E05 720p HDTV DD5.1" should not have been rejected'
        assert entry['quality'].audio == 'dd5.1', 'audio should have been parsed as dd5.1'
