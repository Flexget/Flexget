from __future__ import unicode_literals, division, absolute_import
from flexget.entry import Entry


class TestLazyFields(object):

    def test_lazy_queue(self):
        """Tests behavior when multiple plugins register lazy lookups for the same field"""

        def lazy_a(entry, field):
            if field == 'a_fail':
                entry.unregister_lazy_fields(['ab_field', 'a_field', 'a_fail'], lazy_a)
                return None
            for f in ['a_field', 'ab_field']:
                entry[f] = 'a'
            return entry[field]

        def lazy_b(entry, field):
            for f in ['b_field', 'ab_field', 'a_fail']:
                entry[f] = 'b'
            return entry[field]

        def setup_entry():
            entry = Entry()
            entry.register_lazy_fields(['ab_field', 'a_field', 'a_fail'], lazy_a)
            entry.register_lazy_fields(['ab_field', 'b_field', 'a_fail'], lazy_b)
            return entry

        entry = setup_entry()
        assert entry['b_field'] == 'b', 'Lazy lookup failed'
        assert entry['ab_field'] == 'b', 'ab_field should be `b` when lazy_b is run first'
        # Now cause 'a' lookup to occur
        assert entry['a_field'] == 'a'
        # TODO: What is the desired result when a lookup has information that is already populated?
        #assert entry['ab_field'] == 'b'

        # Test fallback when first lookup fails
        entry = setup_entry()
        assert entry['a_fail'] == 'b', 'Lookup should have fallen back to b'
        assert 'a_field' not in entry, 'a_field should no longer be in entry after failed lookup'
        assert entry['ab_field'] == 'b', 'ab_field should be `b`'
