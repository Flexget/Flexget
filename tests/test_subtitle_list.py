from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import datetime
import os
import sys

import pytest

from flexget.manager import Session

try:
    import babelfish
    import subliminal
except ImportError:
    subliminal = babelfish = None


class TestSubtitleList(object):
    config = """
         templates:
           global:
             mock:
               - {title: 'Movie', location: 'movie.mkv'}
               - {title: 'Series', location: 'series.mkv'}
             accept_all: yes
             seen: local
         tasks:
           subtitle_add:
             list_add:
               - subtitle_list:
                   list: test
           subtitle_emit:
             disable: builtins
             template: no_global
             subtitle_list:
               list: test
           subtitle_remove:
             #subtitle_list:
             #  list: test
             #accept_all: yes
             list_remove:
               - subtitle_list:
                   list: test
           subtitle_fail:
             template: no_global
             subtitle_list:
               list: test
             subliminal:
               languages: [en, afr]
               exact_match: no
               providers:
                 - opensubtitles
             list_queue:
               - subtitle_list:
                   list: test
             rerun: 0
           subtitle_success:
             template: no_global
             subtitle_list:
               list: test
             subliminal:
               languages: [en, ja]
               exact_match: no
               providers:
                 - opensubtitles
             list_queue:
               - subtitle_list:
                   list: test
             rerun: 0
           subtitle_add_with_languages:
             list_add:
               - subtitle_list:
                   list: test
                   languages:
                     - en
                     - eng
           subtitle_add_local_file:
             disable: seen
             template: no_global
             mock:
               - {title: 'The Walking Dead S06E08', location:
                  'tvmaze_test_dir/shows/The walking dead/The.Walking.Dead.S06E08.Start.to.Finish-SiCKBEARD.mp4'}
             accept_all: yes
             list_add:
               - subtitle_list:
                   list: test
           subtitle_add_another_local_file:
             disable: seen
             template: no_global
             mock:
               - {title: "Marvel's Jessica Jones S01E02",
                  location: "tvmaze_test_dir/shows/Marvel's Jessica Jones/
                             Marvels.Jessica.Jones.S01E02.PROPER.720p.WEBRiP.x264-QCF.mkv"}
             accept_all: yes
             list_add:
               - subtitle_list:
                   list: test

    """

    # def test_subtitle_queue_add(self, execute_task):
    #     task = execute_task('subtitle_add')
    #     assert len(task.entries) == 1, 'One movie should have been accepted.'
    #
    #     entry = task.entries[0]
    #     assert entry.accepted
    #
    #     queue = queue_get()
    #     assert len(queue) == 1, 'Accepted movie should be in queue after task is done.'
    #
    #     task = execute_task('subtitle_add')
    #     assert len(task.entries) == 0, 'Movie should only be accepted once'
    #
    #     queue = queue_get()
    #     assert len(queue) == 1
    #
    #     langs = queue[0].languages
    #
    #     assert len(langs) == 0, 'There should be no default language.'

    def test_subtitle_list_del(self, execute_task):
        task = execute_task('subtitle_add')
        task = execute_task('subtitle_emit')
        assert len(task.entries) == 2

        task = execute_task('subtitle_remove')
        task = execute_task('subtitle_emit')
        assert len(task.entries) == 0

    def test_subtitle_list_unique_lang(self, execute_task):
        task = execute_task('subtitle_add_with_languages')

    # def test_subtitle_queue_old(self, execute_task):
    #     config = {}
    #     config['stop_after'] = "7 days"
    #
    #     queue_add('./series.mkv', 'Series', config)
    #
    #     with Session() as session:
    #         s = session.query(QueuedSubtitle).first()
    #         s.added = datetime.datetime.now() + datetime.timedelta(-8)
    #
    #     task = execute_task('subtitle_emit')
    #     assert len(task.entries) == 0, 'Old entry should not be emitted.'
    #
    #     assert len(queue_get()) == 0, 'Old entry should have been removed.'

    # def test_subtitle_queue_update(self, execute_task):
    #     config = {}
    #     config['languages'] = ['en', 'eng']
    #
    #     queue_add('./movie.mkv', 'Movie', config)
    #     assert queue_get()[0].stop_after == "7 days"
    #
    #     config['stop_after'] = "15 days"
    #     queue_add('./movie.mkv', 'Movie', config)
    #     assert queue_get()[0].stop_after == "15 days", 'File\'s stop_after field should have been updated.'

    # def test_subtitle_queue_torrent(self, execute_task):
    #     assert len(queue_get()) == 0, "Queue should be empty before run."
    #     task = execute_task('subtitle_single_file_torrent')
    #
    #     queue = queue_get()
    #     assert len(queue) == 1, 'Task should have accepted one item.'
    #
    #     assert queue[0].path == normalize_path(os.path.join('/', 'ubuntu-12.04.1-desktop-i386.iso')), \
    #         'Queued path should be /ubuntu-12.04.1-desktop-i386.iso'
    #
    # def test_subtitle_queue_multi_file_torrent(self, execute_task):
    #     assert len(queue_get()) == 0, "Queue should be empty before run."
    #     task = execute_task('subtitle_torrent')
    #
    #     queue = queue_get()
    #     assert len(queue) == 1, 'Task should have queued one item.'
    #
    #     assert queue[0].path == normalize_path(os.path.join('/', 'slackware-14.1-iso')), \
    #         'Queued path should be torrent name in root dir'
    #
    #     assert queue[0].alternate_path == normalize_path(os.path.join('~/', 'slackware-14.1-iso')), \
    #         'Queued path should be torrent name in user dir'

    # Skip if subliminal is not installed or if python version <2.7
    @pytest.mark.online
    @pytest.mark.skipif(sys.version_info < (2, 7), reason='requires python2.7')
    @pytest.mark.skipif(not subliminal, reason='requires subliminal')
    def test_subtitle_list_subliminal_fail(self, execute_task):
        task = execute_task('subtitle_add_with_languages')

        assert len(task.entries) == 2, 'Task should have two entries.'

        task = execute_task('subtitle_fail')
        assert len(task.failed) == 2, 'Entries should fail since the files are not valid.'

    # Skip if subliminal is not installed or if python version <2.7
    @pytest.mark.online
    @pytest.mark.skipif(sys.version_info < (2, 7), reason='requires python2.7')
    @pytest.mark.skipif(not subliminal, reason='requires subliminal')
    def test_subtitle_list_subliminal_semi_fail(self, execute_task):
        task = execute_task('subtitle_add_local_file')

        assert len(task.entries) == 1, 'Task should have accepted walking dead local file'

        task = execute_task('subtitle_fail')
        assert len(task.failed) == 1, 'Only one language should have been downloaded which results in failure'
        try:
            os.remove('tvmaze_test_dir/shows/The walking dead/The.Walking.Dead.S06E08.Start.to.Finish-SiCKBEARD.en.srt')
        except OSError:
            pass

    # Skip if subliminal is not installed or if python version <2.7
    @pytest.mark.online
    @pytest.mark.skipif(sys.version_info < (2, 7), reason='requires python2.7')
    @pytest.mark.skipif(not subliminal, reason='requires subliminal')
    def test_subtitle_list_subliminal_success(self, execute_task):
        task = execute_task('subtitle_add_local_file')
        assert len(task.entries) == 1, 'Task should have accepted walking dead local file'

        task = execute_task('subtitle_add_another_local_file')
        assert len(task.entries) == 1, 'Task should have accepted jessica jones file'

        task = execute_task('subtitle_success')
        assert len(task.failed) == 1, 'Should have found both languages for walking dead but not for jessica jones'

        task = execute_task('subtitle_emit')
        assert len(task.entries) == 1, 'Walking Dead should have been removed from the list'
        try:
            os.remove('tvmaze_test_dir/shows/The walking dead/The.Walking.Dead.S06E08.Start.to.Finish-SiCKBEARD.en.srt')
        except OSError:
            pass
        try:
            os.remove('tvmaze_test_dir/shows/The walking dead/The.Walking.Dead.S06E08.Start.to.Finish-SiCKBEARD.ja.srt')
        except OSError:
            pass
