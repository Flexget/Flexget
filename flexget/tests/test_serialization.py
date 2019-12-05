import datetime

from flexget import entry
from flexget.utils import qualities


class TestSerialization:
    def test_entry_serialization(self):
        entry1 = entry.Entry({
            'title': 'blah',
            'url': 'http://blah',
            'listfield': ['a', 'b', 1, 2],
            'dictfield': {'a': 1, 'b': 2},
            'intfield': 5,
            'floatfield': 5.5,
            'datefield': datetime.date(1999, 9, 9),
            'datetimefield': datetime.datetime(1999, 9, 9, 9, 9),
            'qualityfield': qualities.Quality('720p hdtv'),
            'nestedlist': [qualities.Quality('1080p')],
            'nesteddict': {'a': datetime.date(1999, 9, 9)},
        })
        serialized = entry1.dumps()
        print(serialized)
        entry2 = entry.Entry.loads(serialized)
        # Use the underlying dict, so we compare all fields
        assert entry1.store == entry2.store
