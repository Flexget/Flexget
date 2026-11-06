from datetime import UTC, datetime
from unittest import mock

from flexget.plugins.input.torznab import Torznab

FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:torznab="http://torznab.com/schemas/2015/feed">
  <channel>
    <item>
      <title>Some.Show.S01E01.720p</title>
      <guid>https://indexer.example/details/123</guid>
      <link>https://indexer.example/download/123</link>
      <comments>https://indexer.example/details/123#comments</comments>
      <pubDate>Mon, 02 Nov 2026 10:30:00 +0100</pubDate>
      <description>A description</description>
      <enclosure url="https://indexer.example/dl/123.torrent" length="1024"
                 type="application/x-bittorrent"/>
      <torznab:attr name="seeders" value="5"/>
    </item>
    <item>
      <title>Other.Show.S01E01.720p</title>
      <pubDate>not a date</pubDate>
      <enclosure url="https://indexer.example/dl/456.torrent" length="2048"
                 type="application/x-bittorrent"/>
    </item>
  </channel>
</rss>
"""


def _entries():
    task = mock.Mock()
    task.requests.get.return_value.content = FEED
    torznab = Torznab()
    torznab.timeout = 30
    return torznab.create_entries_from_query('https://indexer.example/api', task)


class TestTorznabItemFields:
    def test_standard_item_elements(self):
        entry = _entries()[0]
        assert entry['url'] == 'https://indexer.example/dl/123.torrent'
        assert entry['guid'] == 'https://indexer.example/details/123'
        assert entry['link'] == 'https://indexer.example/download/123'
        assert entry['comments'] == 'https://indexer.example/details/123#comments'
        assert entry['description'] == 'A description'
        assert entry['rss_pubdate'] == datetime(2026, 11, 2, 9, 30, tzinfo=UTC)
        assert entry['torrent_seeds'] == 5

    def test_missing_or_invalid_elements(self):
        entry = _entries()[1]
        assert entry['title'] == 'Other.Show.S01E01.720p'
        for field in ('guid', 'link', 'comments', 'rss_pubdate'):
            assert field not in entry
