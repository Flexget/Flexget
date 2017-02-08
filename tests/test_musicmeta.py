from __future__ import unicode_literals, division, absolute_import
import logging
from tests import FlexGetBase

log = logging.getLogger('test.music_metainfo')


class TestMusicMetaInfo(FlexGetBase):
    """
    Music meta plugin don't parse entries himself (it use parsing plugin to
    get the user/default music parser), so this test don't check music parsing.
    This check that plugin populate entries with infos given by the music parser.
    """
    __yaml__ = """
        tasks:
          populate:
            mock:
              - {title: 'Vitaa - Celle Que Je Vois - 320 Kbps - MP3 - 2009'}
            music: yes

          disabling:
            mock:
              - {title: 'Babar - Guide de la tromperie - 128 Kbps - MP3 - 1985'}
            music: no
    """

    def test_populate_entry(self):
        self.execute_task('populate')
        assert len(self.task.entries) == 1, "This should not append"
        assert self.task.find_entry(music_guessed=True), "music_guessed is missing"
        assert self.task.find_entry(year=2009), "year is missing"
        assert self.task.find_entry(music_title='Celle Que Je Vois'), "music_title is missing"
        assert self.task.find_entry(music_artist='Vitaa'), "music_artist is missing"

    def test_disabling(self):
        self.execute_task('disabling')
        assert len(self.task.entries) == 1, "This should not append"
        assert self.task.find_entry(music_guessed=True) is None, "music_guessed be found"
        assert self.task.find_entry(year=2009) is None, "year be found"
        assert self.task.find_entry(music_title='Celle Que Je Vois') is None, "music_title be found"
        assert self.task.find_entry(music_artist='Vitaa') is None, "music_artist be found"