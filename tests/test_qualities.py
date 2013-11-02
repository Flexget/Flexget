from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase
from flexget.utils.qualities import Quality


class TestQualityModule(object):

    def test_get(self):
        assert not Quality(), 'unknown quality is not false'
        assert Quality('foobar') == Quality(), 'unknown not returned'

    def test_common_name(self):
        for test_val in ('720p', '1280x720'):
            got_val = Quality(test_val).name
            assert got_val == '720p', got_val


class TestQualityParser(object):

    def test_qualities(self):
        items = [('Test.File 1080p.web-dl', '1080p webdl'),
                 ('Test.File.web-dl.1080p', '1080p webdl'),
                 ('Test.File.WebHD.720p', '720p webdl'),
                 ('Test.File.720p.bluray', '720p bluray'),
                 ('Test.File.1080p.bluray', '1080p bluray'),
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

                 ('Test.File.720p.webdl', '720p webdl'),
                 ('Test.File.1280x720_web dl', '720p webdl'),
                 ('Test.File.720p.h264.web.dl', '720p webdl h264'),
                 ('Test.File.1080p.web.x264', '1080p webdl h264'),
                 ('Test.File.web-dl', 'webdl'),
                 ('Test.File.720P', '720p'),
                 ('Test.File.1920x1080', '1080p'),
                 ('Test.File.1080i', '1080i'),
                 ('Test File blurayrip', 'bluray'),
                 ('Test.File.br-rip', 'bluray'),
                 ('Test.File.720px', '720p'),

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
                 ('Test.File.ts.dvdrip.avi', 'ts'),
                 ('Test.File.HDTS.blah', 'ts'),
                 ('Test.File.HDCAM.bluray.lie', 'cam'),

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
                 ('Test.File.truehd', 'truehd')]

        for item in items:
            quality = Quality(item[0]).name
            assert quality == item[1], '`%s` quality should be `%s` not `%s`' % (item[0], item[1], quality)


class TestFilterQuality(FlexGetBase):

    __yaml__ = """
        templates:
          global:
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
    """

    def test_quality(self):
        self.execute_task('qual')
        entry = self.task.find_entry('rejected', title='Smoke.cam')
        assert entry, 'Smoke.cam should have been rejected'

        entry = self.task.find_entry(title='Smoke.1280x720')
        assert entry, 'entry not found?'
        assert entry in self.task.accepted, '720p should be accepted'
        assert len(self.task.rejected) == 2, 'wrong number of entries rejected'
        assert len(self.task.accepted) == 2, 'wrong number of entries accepted'

    def test_min(self):
        self.execute_task('min')
        entry = self.task.find_entry('rejected', title='Smoke.HDTV')
        assert entry, 'Smoke.HDTV should have been rejected'

        entry = self.task.find_entry(title='Smoke.1280x720')
        assert entry, 'entry not found?'
        assert entry in self.task.accepted, '720p should be accepted'
        assert len(self.task.rejected) == 2, 'wrong number of entries rejected'
        assert len(self.task.accepted) == 2, 'wrong number of entries accepted'

    def test_max(self):
        self.execute_task('max')
        entry = self.task.find_entry('rejected', title='Smoke.1280x720')
        assert entry, 'Smoke.1280x720 should have been rejected'

        entry = self.task.find_entry(title='Smoke.cam')
        assert entry, 'entry not found?'
        assert entry in self.task.accepted, 'cam should be accepted'
        assert len(self.task.rejected) == 3, 'wrong number of entries rejected'
        assert len(self.task.accepted) == 1, 'wrong number of entries accepted'

    def test_min_max(self):
        self.execute_task('min_max')
        entry = self.task.find_entry('rejected', title='Smoke.1280x720')
        assert entry, 'Smoke.1280x720 should have been rejected'

        entry = self.task.find_entry(title='Smoke.HR')
        assert entry, 'entry not found?'
        assert entry in self.task.accepted, 'HR should be accepted'
        assert len(self.task.rejected) == 3, 'wrong number of entries rejected'
        assert len(self.task.accepted) == 1, 'wrong number of entries accepted'
