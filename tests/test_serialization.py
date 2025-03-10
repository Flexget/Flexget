import datetime

import pytest

from flexget import entry
from flexget.utils import qualities, serialization


@entry.register_lazy_lookup('lazy function')
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

    def test_builtin_serialization(self):
        # Also test these things nest properly
        value = {
            'a': 'aoeu',
            'b': [1, 2, 3.5],
            'c': (1, datetime.datetime(2019, 12, 12, 12, 12)),
            'd': {'a', 1, datetime.date(2019, 11, 11)},
        }
        out = serialization.dumps(value)
        backin = serialization.loads(out)
        assert backin == value

    def test_unserializable(self):
        # Hide an unserializable object as deep as we can in supported collections
        value = ['a', ('b', {'c': {'d', object()}})]
        with pytest.raises(TypeError):
            serialization.serialize(value)
        with pytest.raises(TypeError):
            serialization.dumps(value)
