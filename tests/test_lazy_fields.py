from __future__ import unicode_literals, division, absolute_import
from builtins import *

from flexget.entry import Entry
from flexget.plugin import PluginError


class TestLazyFields(object):

    def test_lazy_queue(self):
        """Tests behavior when multiple plugins register lazy lookups for the same field"""

        def lazy_a(entry):
            if 'fail' in entry:
                raise PluginError('oh no!')
            for f in ['a_field', 'ab_field', 'a_fail']:
                entry[f] = 'a'

        def lazy_b(entry):
            for f in ['b_field', 'ab_field', 'a_fail']:
                entry[f] = 'b'

        def setup_entry():
            entry = Entry()
            entry.register_lazy_func(lazy_a, ['ab_field', 'a_field', 'a_fail'])
            entry.register_lazy_func(lazy_b, ['ab_field', 'b_field', 'a_fail'])
            return entry

        entry = setup_entry()
        assert entry['b_field'] == 'b', 'Lazy lookup failed'
        assert entry['ab_field'] == 'b', 'ab_field should be `b` when lazy_b is run first'
        # Now cause 'a' lookup to occur
        assert entry['a_field'] == 'a'
        # TODO: What is the desired result when a lookup has information that is already populated?
        # assert entry['ab_field'] == 'b'

        # Test fallback when first lookup fails
        entry = setup_entry()
        entry['fail'] = True
        assert entry['a_fail'] == 'b', 'Lookup should have fallen back to b'
        assert entry['a_field'] is None, 'a_field should be None after failed lookup'
        assert entry['ab_field'] == 'b', 'ab_field should be `b`'
