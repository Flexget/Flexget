from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import datetime
import os
import sys

import pytest

from flexget.manager import Session
from flexget.plugins.list.subtitle_list import SubtitleListFile, SubtitleListLanguage, normalize_path

try:
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
               languages: [en]

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
             list_match:
               from:
                 - subtitle_list:
                     list: test
               single_match: yes
             rerun: 0

           subtitle_simulate_success:
             template: no_global
             subtitle_list:
               list: test
             subliminal:
               languages: [en, ja]
               exact_match: no
               providers:
                 - opensubtitles
             list_match:
               from:
                 - subtitle_list:
                     list: test
               single_match: yes
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
                  'subtitle_list_test_dir/The.Walking.Dead.S06E08-FlexGet.mp4'}
             accept_all: yes
             list_add:
               - subtitle_list:
                   list: test
                   languages: [en, ja]

           subtitle_add_another_local_file:
             disable: seen
             template: no_global
             mock:
               - {title: "Marvel's Jessica Jones S01E02",
                  location: "subtitle_list_test_dir/Marvels.Jessica.Jones.S01E02-FlexGet.mkv"}
             accept_all: yes
             list_add:
               - subtitle_list:
                   list: test
                   languages: [en, ja]

           subtitle_add_a_third_local_file:
             disable: seen
             template: no_global
             mock:
               - {title: "The.Big.Bang.Theory.S09E09",
                  location: "subtitle_list_test_dir/The.Big.Bang.Theory.S09E09-FlexGet.mkv"}
             accept_all: yes
             list_add:
               - subtitle_list:
                   list: test

           subtitle_test_expiration_add:
             disable: builtins
             template: no_global
             mock:
               - {title: "The.Big.Bang.Theory.S09E09",
                  location: "subtitle_list_test_dir/The.Big.Bang.Theory.S09E09-FlexGet.mkv"}
             accept_all: yes
             list_add:
               - subtitle_list:
                   list: test
                   remove_after: 7 days

           subtitle_add_local_dir:
             disable: builtins
             template: no_global
             mock:
               - {title: "My Videos", location: "subtitle_list_test_dir"}
             list_add:
               - subtitle_list:
                   list: test
                   allow_dir: yes
                   languages: ['ja']
             accept_all: yes

           subtitle_emit_dir:
             disable: builtins
             template: no_global
             subtitle_list:
               list: test
               languages: [en]

           subtitle_simulate_success_no_check:
             template: no_global
             subtitle_list:
               list: test
               check_subtitles: no
             subliminal:
               languages: [ja]
               exact_match: no
               providers:
                 - opensubtitles
             list_match:
               from:
                 - subtitle_list:
                     list: test
               single_match: yes

           subtitle_add_force_file:
             disable: builtins
             template: no_global
             mock:
               - {title: "The.Walking.Dead.S06E09-FlexGet",
                  location: "subtitle_list_test_dir/The.Walking.Dead.S06E09-FlexGet.mp4"}
             list_add:
               - subtitle_list:
                   list: test
                   allow_dir: yes
                   languages: ['ja']
             accept_all: yes

           subtitle_add_force_file_no:
             disable: builtins
             template: no_global
             mock:
               - {title: "The.Walking.Dead.S06E09-FlexGet",
                  location: "subtitle_list_test_dir/The.Walking.Dead.S06E09-FlexGet.mp4"}
             list_add:
               - subtitle_list:
                   list: test
                   languages: ['ja']
                   force_file_existence: no
             accept_all: yes

           subtitle_emit_force_no:
             disable: builtins
             template: no_global
             subtitle_list:
               list: test
               force_file_existence: no

           subtitle_path:
             disable: builtins
             template: no_global
             mock:
               - {title: "The.Walking.Dead.S06E08-FlexGet",
                  output: 'subtitle_list_test_dir/The.Walking.Dead.S06E08-FlexGet.mp4'}
             list_add:
               - subtitle_list:
                   list: test
                   path: '{{ output }}'
             accept_all: yes

           subtitle_path_relative:
             disable: builtins
             template: no_global
             mock:
               - {title: "The.Walking.Dead.S06E08-FlexGet"}
             list_add:
               - subtitle_list:
                   list: test
                   path: 'subtitle_list_test_dir/The.Walking.Dead.S06E08-FlexGet.mp4'
             accept_all: yes
    """

    def test_subtitle_list_del(self, execute_task):
        task = execute_task('subtitle_add')
        task = execute_task('subtitle_emit')
        assert len(task.entries) == 2

        task = execute_task('subtitle_remove')
        task = execute_task('subtitle_emit')
        assert len(task.entries) == 0

    def test_subtitle_list_unique_lang(self, execute_task):
        execute_task('subtitle_add_with_languages')

        with Session() as session:
            s = session.query(SubtitleListLanguage).all()

            assert s[0].file.title != s[1].file.title, 'There should only be one row per entry as "en" and "eng" are eq'
            assert len(s) == 2, 'Language "en" and "eng" are equivalent and only one should exist per entry'

    def test_subtitle_list_old(self, execute_task):
        task = execute_task('subtitle_test_expiration_add')

        with Session() as session:
            s = session.query(SubtitleListFile).first()
            s.added = datetime.datetime.now() + datetime.timedelta(-8)

        task = execute_task('subtitle_emit')
        assert len(task.entries) == 0, 'File should have expired.'

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
    @pytest.skip
    @pytest.mark.online
    @pytest.mark.skipif(sys.version_info < (2, 7), reason='requires python2.7')
    @pytest.mark.skipif(not subliminal, reason='requires subliminal')
    def test_subtitle_list_subliminal_semi_fail(self, execute_task):
        task = execute_task('subtitle_add_local_file')

        assert len(task.entries) == 1, 'Task should have accepted walking dead local file'

        task = execute_task('subtitle_fail')

        # cleanup
        try:
            os.remove('subtitle_list_test_dir/The.Walking.Dead.S06E08-FlexGet.en.srt')
        except OSError:
            pass

        assert len(task.failed) == 1, 'Only one language should have been downloaded which results in failure'

    # Skip if subliminal is not installed or if python version <2.7
    @pytest.mark.skip(reason="Test sporadically fails")
    # @pytest.mark.skipif(sys.version_info < (2, 7), reason='requires python2.7')
    # @pytest.mark.skipif(not subliminal, reason='requires subliminal')
    def test_subtitle_list_subliminal_success(self, execute_task):
        task = execute_task('subtitle_add_local_file')
        assert len(task.entries) == 1, 'Task should have accepted walking dead local file'

        task = execute_task('subtitle_add_another_local_file')
        assert len(task.entries) == 1, 'Task should have accepted jessica jones file'

        with open('subtitle_list_test_dir/The.Walking.Dead.S06E08-FlexGet.en.srt', 'a'):
            os.utime('subtitle_list_test_dir/The.Walking.Dead.S06E08-FlexGet.en.srt', None)

        with open('subtitle_list_test_dir/The.Walking.Dead.S06E08-FlexGet.ja.srt', 'a'):
            os.utime('subtitle_list_test_dir/The.Walking.Dead.S06E08-FlexGet.ja.srt', None)

        with open('subtitle_list_test_dir/Marvels.Jessica.Jones.S01E02-FlexGet.en.srt', 'a'):
            os.utime('subtitle_list_test_dir/Marvels.Jessica.Jones.S01E02-FlexGet.en.srt', None)

        task = execute_task('subtitle_simulate_success')
        assert len(task.failed) == 1, 'Should have found both languages for walking dead but not for jessica jones'

        task = execute_task('subtitle_emit')
        assert len(task.entries) == 1, 'Walking Dead should have been removed from the list'
        try:
            os.remove('subtitle_list_test_dir/The.Walking.Dead.S06E08-FlexGet.en.srt')
        except OSError:
            pass
        try:
            os.remove('subtitle_list_test_dir/The.Walking.Dead.S06E08-FlexGet.ja.srt')
        except OSError:
            pass
        try:
            os.remove('subtitle_list_test_dir/Marvels.Jessica.Jones.S01E02-FlexGet.en.srt')
        except OSError:
            pass

    # Skip if subliminal is not installed or if python version <2.7
    @pytest.mark.skipif(sys.version_info < (2, 7), reason='requires python2.7')
    @pytest.mark.skipif(not subliminal, reason='requires subliminal')
    def test_subtitle_list_local_subtitles(self, execute_task):
        task = execute_task('subtitle_add_local_file')
        task = execute_task('subtitle_add_another_local_file')
        task = execute_task('subtitle_add_a_third_local_file')

        task = execute_task('subtitle_emit')
        assert len(task.entries) == 2, 'Big Bang Theory already has a local subtitle and should have been removed.'

    def test_subtitle_list_local_dir(self, execute_task):
        task = execute_task('subtitle_add_local_dir')

        with Session() as session:
            s = session.query(SubtitleListFile).first()
            assert s.title == 'My Videos', 'Should have added the dir with title "My Videos" to the list'

        task = execute_task('subtitle_emit_dir')

        assert len(task.entries) == 3, 'Should have found 3 video files and the containing dir should not be included.'

    # Skip if subliminal is not installed or if python version <2.7
    @pytest.mark.skipif(sys.version_info < (2, 7), reason='requires python2.7')
    @pytest.mark.skipif(not subliminal, reason='requires subliminal')
    def test_subtitle_list_subliminal_dir_success(self, execute_task):
        task = execute_task('subtitle_add_local_dir')

        with open('subtitle_list_test_dir/The.Walking.Dead.S06E08-FlexGet.ja.srt', 'a'):
            os.utime('subtitle_list_test_dir/The.Walking.Dead.S06E08-FlexGet.ja.srt', None)

        with open('subtitle_list_test_dir/Marvels.Jessica.Jones.S01E02-FlexGet.ja.srt', 'a'):
            os.utime('subtitle_list_test_dir/Marvels.Jessica.Jones.S01E02-FlexGet.ja.srt', None)

        with open('subtitle_list_test_dir/The.Big.Bang.Theory.S09E09-FlexGet.ja.srt', 'a'):
            os.utime('subtitle_list_test_dir/The.Big.Bang.Theory.S09E09-FlexGet.ja.srt', None)

        task = execute_task('subtitle_simulate_success_no_check')
        assert len(task.all_entries) == 3, '"My Videos" should have been deleted'
        assert len(task.accepted) == 3, 'All files have all subtitles'

        with Session() as session:
            s = session.query(SubtitleListFile).first()
            assert s is None, '"My Videos" and contained files should have been deleted from the list'

        try:
            os.remove('subtitle_list_test_dir/The.Walking.Dead.S06E08-FlexGet.ja.srt')
        except OSError:
            pass
        try:
            os.remove('subtitle_list_test_dir/Marvels.Jessica.Jones.S01E02-FlexGet.ja.srt')
        except OSError:
            pass
        try:
            os.remove('subtitle_list_test_dir/The.Big.Bang.Theory.S09E09-FlexGet.ja.srt')
        except OSError:
            pass

    def test_subtitle_list_force_file_existence_no(self, execute_task):
        task = execute_task('subtitle_add_force_file_no')

        assert not os.path.exists(task.entries[0]['location']), 'File should not exist.'

        with Session() as session:
            s = session.query(SubtitleListFile).first()
            assert s, 'The file should have been added to the list even though it does not exist'

        task = execute_task('subtitle_emit_force_no')

        assert len(task.entries) == 0, 'List should not be empty, but since file does not exist it isn\' returned'

        with Session() as session:
            s = session.query(SubtitleListFile).first()
            assert s, 'The file should still be in the list'

    def test_subtitle_list_force_file_existence_yes(self, execute_task):
        task = execute_task('subtitle_add_force_file')

        assert not os.path.exists(task.entries[0]['location']), 'File should not exist.'

        with Session() as session:
            s = session.query(SubtitleListFile).first()
            assert s is None, 'The file should not have been added to the list as it does not exist'

        task = execute_task('subtitle_emit')

        assert len(task.entries) == 0, 'List should be empty'

    def test_subtitle_list_force_file_existence_yes_input(self, execute_task):
        task = execute_task('subtitle_add_force_file_no')

        assert not os.path.exists(task.entries[0]['location']), 'File should not exist.'

        with Session() as session:
            s = session.query(SubtitleListFile).first()
            assert s, 'The file should have been added to the list even though it does not exist'

        task = execute_task('subtitle_emit')

        assert len(task.entries) == 0, 'No input should be returned as the file does not exist'

        with Session() as session:
            s = session.query(SubtitleListFile).first()
            assert s is None, 'The file should have been removed from the list since it does not exist'

    def test_subtitle_list_path(self, execute_task):
        execute_task('subtitle_path')

        with Session() as session:
            s = session.query(SubtitleListFile).first()
            assert s, 'The file should have been added to the list'
            assert s.location == normalize_path('subtitle_list_test_dir/The.Walking.Dead.S06E08-FlexGet.mp4'), \
                'location should be what the output field was set to'

    def test_subtitle_list_relative_path(self, execute_task):
        execute_task('subtitle_path_relative')

        with Session() as session:
            s = session.query(SubtitleListFile).first()
            assert s, 'The file should have been added to the list'
            assert s.location == normalize_path('subtitle_list_test_dir/The.Walking.Dead.S06E08-FlexGet.mp4'), \
                'location should be what the output field was set to'
