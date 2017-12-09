from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import pytest

from flexget.manager import Session
from flexget.plugins.filter.upgrade import EntryUpgrade


class TestUpgrade(object):
    config = """
        tasks:
          first_download:
            accept_all: yes
            mock:
              - {title: 'Smoke.720p.WEB-DL.X264.AC3', 'id': 'Smoke'}
          no_tracking:
            accept_all: yes
            upgrade:
              tracking: no
            mock:
              - {title: 'Smoke.BRRip.x264.720p', 'id': 'Smoke'}
          identified_by:
            upgrade:
              identified_by: "{{ movie_name }}"
            mock:
              - {title: 'Smoke.1080p.BRRip.X264.AC3', 'id': 'Smoke', 'movie_name': 'Smoke'}
          upgrade_quality:
            upgrade: yes
            mock:
              - {title: 'Smoke.1080p.720p WEB-DL X264 AC3', 'id': 'Smoke'}
              - {title: 'Smoke.720p.WEB-DL.X264.AC3', 'id': 'Smoke'}
              - {title: 'Smoke.BRRip.x264.720p', 'id': 'Smoke'}
          reject_lower:
            upgrade:
              on_lower: reject
            mock:
              - {title: 'Smoke.1080p.BRRip.X264.AC3', 'id': 'Smoke'}
              - {title: 'Smoke.1080p.720p WEB-DL X264-EVO', 'id': 'Smoke'}
              - {title: 'Smoke.BRRip.x264.720p', 'id': 'Smoke'}
    """

    def test_learn(self, execute_task):
        execute_task('first_download')
        with Session() as session:
            query = session.query(EntryUpgrade).all()
            assert len(query) == 1, 'There should be one tracked entity present.'
            assert query[0].id == 'smoke', 'Should of tracked name `Smoke`.'

    def test_no_tracking(self, execute_task):
        execute_task('no_tracking')
        with Session() as session:
            assert len(session.query(EntryUpgrade).all()) == 0, 'There should be one tracked entity present.'

    def test_identified_by(self, execute_task):
        execute_task('first_download')
        task = execute_task('identified_by')
        entry = task.find_entry('accepted', title='Smoke.1080p.BRRip.X264.AC3')
        assert entry, 'Smoke.1080p.BRRip.X264.AC3 should have been accepted'

    def test_upgrade_quality(self, execute_task):
        execute_task('first_download')
        task = execute_task('upgrade_quality')
        entry = task.find_entry('accepted', title='Smoke.1080p.720p WEB-DL X264 AC3')
        assert entry, 'Smoke.1080p.720p WEB-DL X264 AC3 should have been accepted'

    def test_reject_lower(self, execute_task):
        execute_task('first_download')
        task = execute_task('reject_lower')
        entry = task.find_entry('accepted', title='Smoke.1080p.BRRip.X264.AC3')
        assert entry, 'Smoke.1080p.BRRip.X264.AC3 should have been accepted'
        entry = task.find_entry('rejected', title='Smoke.1080p.720p WEB-DL X264-EVO')
        assert entry, 'Smoke.1080p.720p WEB-DL X264-EVO should have been rejected'
        entry = task.find_entry('rejected', title='Smoke.BRRip.x264.720p')
        assert entry, 'Smoke.BRRip.x264.720p should have been rejected'


class TestUpgradeIdentifiers(object):
    config = """
        tasks:
          imdb_download:
            accept_all: yes
            imdb_lookup: yes
            mock:
              - {title: 'Smoke.720p.WEB-DL.X264.AC3'}
          imdb_upgrade:
            accept_all: yes
            imdb_lookup: yes
            mock:
              - {title: 'Smoke.1080p.BRRip.X264.AC3'}
    """

    @pytest.mark.online
    def test_imdb(self, execute_task):
        execute_task('imdb_download')
        task = execute_task('imdb_upgrade')
        entry = task.find_entry('accepted', title='Smoke.1080p.BRRip.X264.AC3')
        assert entry, 'Smoke.1080p.BRRip.X264.AC3 should have been accepted'
