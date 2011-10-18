from tests import FlexGetBase
from flexget.utils import qualities as quals


class TestQualityParser(object):

    def test_qualities(self):
        items = [('Test.File 1080p.web-dl', '1080p web-dl'),
                 ('Test.File.web-dl.1080p', '1080p web-dl'),
                 ('Test.File.720p.bluray', '720p bluray'),
                 ('Test.File.1080p.bluray', '1080p bluray'),

                 ('Test.File.720p.bluray.r5', '720p bluray rc'),
                 ('Test.File.1080p.bluray.rc', '1080p bluray rc'),

                 # 10bit
                 ('Test.File.480p.10bit', '480p 10bit'),
                 ('Test.File.720p.10bit', '720p 10bit'),
                 ('Test.File.720p.bluray.10bit', '720p bluray 10bit'),
                 ('Test.File.1080p.10bit', '1080p 10bit'),
                 ('Test.File.1080p.bluray.10bit', '1080p bluray 10bit'),

                 ('Test.File.720p.webdl', '720p web-dl'),
                 ('Test.File.1280x720_web dl', '720p web-dl'),
                 ('Test.File.720p.h264.web.dl', '720p web-dl'),
                 ('Test.File.web-dl', 'web-dl'),
                 ('Test.File.720P', '720p'),
                 ('Test.File.1920x1080', '1080p'),
                 ('Test.File.1080i', '1080i'),
                 ('Test File blurayrip', 'bdrip'),
                 ('Test.File.br-rip', 'bdrip'),

                 ('Test.File.dvd.rip', 'dvdrip'),
                 
                 ('Test.File.[576p][00112233].mkv', '576p'),

                 ('Test.File.360p.avi', '360p'),
                 ('Test.File.[360p].mkv', '360p'),
                 ('Test.File.368.avi', '368p')]

        for item in items:
            quality = quals.parse_quality(item[0]).name
            assert quality == item[1], '`%s` quality should be `%s` not `%s`' % (item[0], item[1], quality)


class TestFilterQuality(FlexGetBase):

    __yaml__ = """
        presets:
          global:
            mock:
              - {title: 'Smoke.1280x720'}
              - {title: 'Smoke.HDTV'}
              - {title: 'Smoke.cam'}
              - {title: 'Smoke.HR'}
            accept_all: yes
        feeds:
          qual:
            quality:
              - hdtv
              - 720p
          min:
            quality:
              min: HR
          max:
            quality:
              max: cam
          min_max:
            quality:
              min: HR
              max: 720i
    """

    def test_quality(self):
        self.execute_feed('qual')
        entry = self.feed.find_entry('rejected', title='Smoke.cam')
        assert entry, 'Smoke.cam should have been rejected'

        entry = self.feed.find_entry(title='Smoke.1280x720')
        assert entry, 'entry not found?'
        assert entry in self.feed.accepted, '720p should be accepted'
        assert len(self.feed.rejected) == 2, 'wrong number of entries rejected'
        assert len(self.feed.accepted) == 2, 'wrong number of entries accepted'

    def test_min(self):
        self.execute_feed('min')
        entry = self.feed.find_entry('rejected', title='Smoke.HDTV')
        assert entry, 'Smoke.HDTV should have been rejected'

        entry = self.feed.find_entry(title='Smoke.1280x720')
        assert entry, 'entry not found?'
        assert entry in self.feed.accepted, '720p should be accepted'
        assert len(self.feed.rejected) == 2, 'wrong number of entries rejected'
        assert len(self.feed.accepted) == 2, 'wrong number of entries accepted'

    def test_max(self):
        self.execute_feed('max')
        entry = self.feed.find_entry('rejected', title='Smoke.1280x720')
        assert entry, 'Smoke.1280x720 should have been rejected'

        entry = self.feed.find_entry(title='Smoke.cam')
        assert entry, 'entry not found?'
        assert entry in self.feed.accepted, 'cam should be accepted'
        assert len(self.feed.rejected) == 3, 'wrong number of entries rejected'
        assert len(self.feed.accepted) == 1, 'wrong number of entries accepted'

    def test_min_max(self):
        self.execute_feed('min_max')
        entry = self.feed.find_entry('rejected', title='Smoke.1280x720')
        assert entry, 'Smoke.1280x720 should have been rejected'

        entry = self.feed.find_entry(title='Smoke.HR')
        assert entry, 'entry not found?'
        assert entry in self.feed.accepted, 'HR should be accepted'
        assert len(self.feed.rejected) == 3, 'wrong number of entries rejected'
        assert len(self.feed.accepted) == 1, 'wrong number of entries accepted'
