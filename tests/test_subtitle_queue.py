from __future__ import unicode_literals, division, absolute_import
from builtins import object

import datetime
import os
import sys

import pytest

from flexget.plugins.filter.subtitle_queue import queue_add, queue_get, QueuedSubtitle, normalize_path
from flexget.manager import Session

try:
    import babelfish
    import subliminal
except ImportError:
    subliminal = babelfish = None


class TestSubtitleQueue(object):
    config = """
         templates:
           global:
             mock:
               - {title: 'Movie', location: 'movie.mkv'}
               #- {title: 'Series', location: 'series.mkv'}
             accept_all: yes
             seen: local
         tasks:
           subtitle_add:
             subtitle_queue:
                action: add
           subtitle_emit:
             template: no_global
             subtitle_queue: emit
           subtitle_remove:
             subtitle_queue:
               action: remove
           subtitle_single_file_torrent:
             template: no_global
             accept_all: yes
             subtitle_queue:
               action: add
               path: '/'
             mock:
               - {title: 'test', file: 'test.torrent'}
           subtitle_torrent:
             template: no_global
             accept_all: yes
             subtitle_queue:
               action: add
               path: '/'
               alternate_path: '~/'
             mock:
               - {title: 'multi', file: 'multi.torrent'}
           subtitle_fail:
             template: no_global
             subtitle_queue: emit
             subliminal:
               languages: [en]
               exact_match: yes
             rerun: 0
    """

    def test_subtitle_queue_add(self, execute_task):
        task = execute_task('subtitle_add')
        assert len(task.entries) == 1, 'One movie should have been accepted.'

        entry = task.entries[0]
        assert entry.accepted

        queue = queue_get()
        assert len(queue) == 1, 'Accepted movie should be in queue after task is done.'

        task = execute_task('subtitle_add')
        assert len(task.entries) == 0, 'Movie should only be accepted once'

        queue = queue_get()
        assert len(queue) == 1

        langs = queue[0].languages

        assert len(langs) == 0, 'There should be no default language.'

    def test_subtitle_queue_emit(self, execute_task):
        config = {}
        config['languages'] = ['en']
        queue_add('./series.mkv', 'Series', config)
        queue_add('./movie.mkv', 'Movie', config)
        queue = queue_get()
        assert len(queue) == 2

        try:
            import subliminal
        except ImportError:
            task = execute_task('subtitle_emit')

            assert len(task.entries) == 2, "2 items should be emitted from the queue."

            queue = queue_get()
            assert len(queue) == 2

        # task = execute_task('subtitle_emit')
        # print len(task.entries)
        # print len(queue_get())
        # assert len(task.entries) == 0, "2 items should be emitted from the queue again."

    def test_subtitle_queue_del(self, execute_task):
        task = execute_task('subtitle_add')
        queue = queue_get()
        assert len(queue) == 1

        task = execute_task('subtitle_remove')
        queue = queue_get()
        assert len(queue) == 0

    def test_subtitle_queue_unique_lang(self, execute_task):
        config = {}
        config['languages'] = ['en', 'eng']

        queue_add('./series.mkv', 'Series', config)
        queue_add('./movie.mkv', 'Movie', config)
        queue_add('./movie.mkv', 'Movie', config)

        queue = queue_get()
        assert len(queue) == 2

        for q in queue:
            assert len(q.languages) == 1

    def test_subtitle_queue_old(self, execute_task):
        config = {}
        config['stop_after'] = "7 days"

        queue_add('./series.mkv', 'Series', config)

        with Session() as session:
            s = session.query(QueuedSubtitle).first()
            s.added = datetime.datetime.now() + datetime.timedelta(-8)

        task = execute_task('subtitle_emit')
        assert len(task.entries) == 0, 'Old entry should not be emitted.'

        assert len(queue_get()) == 0, 'Old entry should have been removed.'

    def test_subtitle_queue_update(self, execute_task):
        config = {}
        config['languages'] = ['en', 'eng']

        queue_add('./movie.mkv', 'Movie', config)
        assert queue_get()[0].stop_after == "7 days"

        config['stop_after'] = "15 days"
        queue_add('./movie.mkv', 'Movie', config)
        assert queue_get()[0].stop_after == "15 days", 'File\'s stop_after field should have been updated.'

    def test_subtitle_queue_torrent(self, execute_task):
        assert len(queue_get()) == 0, "Queue should be empty before run."
        task = execute_task('subtitle_single_file_torrent')

        queue = queue_get()
        assert len(queue) == 1, 'Task should have accepted one item.'

        assert queue[0].path == normalize_path(os.path.join('/', 'ubuntu-12.04.1-desktop-i386.iso')), \
            'Queued path should be /ubuntu-12.04.1-desktop-i386.iso'

    def test_subtitle_queue_multi_file_torrent(self, execute_task):
        assert len(queue_get()) == 0, "Queue should be empty before run."
        task = execute_task('subtitle_torrent')

        queue = queue_get()
        assert len(queue) == 1, 'Task should have queued one item.'

        assert queue[0].path == normalize_path(os.path.join('/', 'slackware-14.1-iso')), \
            'Queued path should be torrent name in root dir'

        assert queue[0].alternate_path == normalize_path(os.path.join('~/', 'slackware-14.1-iso')), \
            'Queued path should be torrent name in user dir'

    # Skip if subliminal is not installed or if python version <2.7
    @pytest.mark.skipif(sys.version_info < (2, 7), reason='requires python2.7')
    @pytest.mark.skipif(not subliminal, reason='requires subliminal')
    def test_subtitle_queue_subliminal_fail(self, execute_task):
        config = {'languages': ['en']}

        queue_add('movie.mkv', 'Movie', config)

        queue = queue_get()
        assert len(queue) == 1, 'Task should have queued one item.'

        task = execute_task('subtitle_fail')
        assert len(task.failed) == 1, 'Entry should fail since the file is not valid.'



