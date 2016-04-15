from __future__ import unicode_literals, division, absolute_import
from builtins import *

import mock
import pytest


@pytest.mark.online
@pytest.mark.usefixtures('tmpdir')
class TestUoccinReader(object):
    config = """
        templates:
          global:
            disable: [seen]
            accept_all: yes
        tasks:
          test_sync:
            filesystem:
              path:
                - '__tmp__'
              regexp: '.*\.diff$'
            uoccin_reader:
              uuid: flexget_test
              path: __tmp__
          test_sync_chk:
            mock:
              - { title: 'Godzilla', imdb_id: 'tt0047034' }
              - { title: 'Dr. Strangelove', imdb_id: 'tt0057012' }
              - { title: 'The Big Bang Theory', tvdb_id: '80379', series_season: 8, series_episode: 24 }
              - { title: 'TURN', tvdb_id: '272135', series_season: 2, series_episode: 5 }
            uoccin_lookup: __tmp__
    """

    @pytest.mark.filecopy([
        ('uoccin/uoccin.diff', '__tmp__/1431093328970.uoccin_test.diff'),
        ('uoccin/uoccin.json', '__tmp__/uoccin/uoccin.json')
    ])
    def test_read(self, execute_task, tmpdir):
        execute_task('test_sync')
        task = execute_task('test_sync_chk')
        entry = task.find_entry(imdb_id='tt0047034')
        assert entry.get('uoccin_watchlist', False), \
            'Expected uoccin_watchlist:True for movie "Godzilla", found %s instead.' % entry.get('uoccin_watchlist')
        entry = task.find_entry(imdb_id='tt0057012')
        assert entry.get('uoccin_collected', False), \
            'Expected uoccin_collected:True for movie "Dr. Strangelove", found %s instead.' % entry.get(
                'uoccin_collected')
        entry = task.find_entry(tvdb_id='80379', series_season=8, series_episode=24)
        assert entry.get('uoccin_watchlist', False), \
            'Expected uoccin_watchlist:True for series "The Big Bang Theory", found %s instead.' % entry.get(
                'uoccin_watchlist')
        assert 'pippo' in entry.get('uoccin_tags', None), \
            'Expected "pippo" in uoccin_tags for series "The Big Bang Theory", found %s instead.' % entry.get(
                'uoccin_tags')
        assert entry.get('uoccin_watched', False), \
            'Expected uoccin_watched:True for episode "The Big Bang Theory S08E24", found %s instead.' % entry.get(
                'uoccin_watched')
        entry = task.find_entry(tvdb_id='272135', series_season=2, series_episode=5)
        assert entry.get('uoccin_collected', False), \
            'Expected uoccin_collected:True for episode "TURN S08E24", found %s instead.' % entry.get(
                'uoccin_collected')
        assert 'ita' in entry.get('uoccin_subtitles', None), \
            'Expected "ita" in uoccin_subtitles for episode "TURN S02E05", found %s instead.' % entry.get(
                'uoccin_subtitles')


@mock.patch('flexget.plugins.api_tvdb.mark_expired')
@pytest.mark.online
@pytest.mark.usefixtures('tmpdir')
class TestUoccinWriters(object):
    config = """
        templates:
          global:
            disable: [seen]
            accept_all: yes
            mock:
              - { title: 'Godzilla', imdb_id: 'tt0047034' }
              - { title: 'Dr. Strangelove', imdb_id: 'tt0057012' }
              - { title: 'The Big Bang Theory', tvdb_id: '80379', series_season: 8, series_episode: 24 }
              - { title: 'TURN', tvdb_id: '272135', series_season: 2, series_episode: 5 }
        tasks:
          test_del:
            uoccin_watchlist_remove:
              uuid: flexget_test
              path: __tmp__
            uoccin_collection_remove:
              uuid: flexget_test
              path: __tmp__
            uoccin_watched_false:
              uuid: flexget_test
              path: __tmp__
          test_chk:
            uoccin_lookup: __tmp__/uoccin
    """

    @pytest.mark.filecopy('uoccin/uoccin.json', '__tmp__/uoccin/uoccin.json')
    def test_write(self, mock_expired, execute_task):
        execute_task('test_del')
        task = execute_task('test_chk')
        entry = task.find_entry(imdb_id='tt0047034')
        assert entry is None or entry.get('uoccin_watchlist', True) == False, \
            'Expected uoccin_watchlist:False for movie "Godzilla", found %s instead.' % entry.get('uoccin_watchlist')
        entry = task.find_entry(imdb_id='tt0057012')
        assert entry is None or entry.get('uoccin_collected', True) == False, \
            'Expected uoccin_collected:False for movie "Dr. Strangelove", found %s instead.' % entry.get(
                'uoccin_collected')
        entry = task.find_entry(tvdb_id='80379', series_season=8, series_episode=24)
        assert entry is None or entry.get('uoccin_watched', True) == False, \
            'Expected uoccin_watched:False for episode "The Big Bang Theory S08E24", found %s instead.' % entry.get(
                'uoccin_watched')
        entry = task.find_entry(tvdb_id='272135', series_season=2, series_episode=5)
        assert entry is None or entry.get('uoccin_collected', True) == False, \
            'Expected uoccin_collected:False for episode "TURN S02E05", found %s instead.' % entry.get(
                'uoccin_collected')
