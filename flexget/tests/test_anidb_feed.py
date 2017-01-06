from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import pytest
from datetime import date


@pytest.mark.online
class TestAnidbFeed(object):
    config = ("""
        templates:
          global:
            headers:
                User-Agent: "Mozilla/5.0"
        tasks:
          test-anidb-feed:
            anidb_feed:
                url: http://anidb.net/feeds/files.atom
    """)

    def test_anidb_feed(self, execute_task):
        task = execute_task('test-anidb-feed')
        assert task.entries, 'no entries created / site may be down'
        # check expected minimum fields and types
        for entry in task.entries:
            assert entry['rss_pubdate'], 'expecting rss_pubdate'
            assert isinstance(entry['rss_pubdate'], date), 'expecting date type for rss_pubdate'
            assert entry['title'], 'expecting title'
            assert entry['content_size'], 'expecting content_size'
            assert type(entry['content_size']) is int, 'expecting int size type for content_size'
            assert entry['anidb_name'], 'expecting anidb_name'
            assert entry['anidb_fid'], 'expecting anidb_fid'
            assert type(entry['content_size']) is int, 'expecting int size type for anidb_fid'
            assert entry['anidb_feed_size'], 'expecting anidb_feed_size'
            assert type(entry['anidb_feed_size']) is int, 'expecting int size type for anidb_feed_size'
