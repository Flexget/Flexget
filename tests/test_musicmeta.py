from __future__ import unicode_literals, division, absolute_import
import logging
from tests import FlexGetBase

log = logging.getLogger('test.music_metainfo')


class TestMusicMetaInfo(FlexGetBase):
    __yaml__ = """
        tasks:
          populate:
            mock:
              - {title: 'Vitaa - Celle Que Je Vois - 320 Kbps - MP3 - 2009'}
            music: yes
    """
    def test_populate_entry(self):
        self.execute_task('populate')
        assert self.task.find_entry(year=2009), "year is missing"
        assert self.task.find_entry(music_title='Celle Que Je Vois'), "music_title is missing"
        assert self.task.find_entry(music_artist='Vitaa'), "music_artist is missing"

