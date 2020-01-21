import datetime

from flexget import entry
from flexget.utils import qualities, serialization


@entry.register_lazy_func('lazy function')
def lazy_func(entry):
    entry['lazyfield'] = 'value a'


class TestSerialization:
    def test_entry_serialization(self):
        entry1 = entry.Entry(
            {
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
            }
        )
        entry1.add_lazy_fields('lazy function', ['lazyfield'])
        assert entry1.is_lazy('lazyfield')
        serialized = serialization.dumps(entry1)
        print(serialized)
        entry2 = serialization.loads(serialized)
        # Use the underlying dict, so we compare all fields
        assert entry2.is_lazy('lazyfield')
        assert dict(entry1) == dict(entry2)
        assert entry2['lazyfield'] == 'value a'
