from flexget.entry import Entry, register_lazy_lookup
from flexget.plugin import PluginError


@register_lazy_lookup('lazy_a')
def lazy_a(entry):
    if 'fail' in entry:
        raise PluginError('oh no!')
    for f in ['a_field', 'ab_field', 'a_fail']:
        entry[f] = 'a'


@register_lazy_lookup('lazy_b')
def lazy_b(entry):
    for f in ['b_field', 'ab_field', 'a_fail']:
        entry[f] = 'b'


class TestLazyFields:
    def test_lazy_queue(self):
        """Tests behavior when multiple plugins register lazy lookups for the same field."""

        def setup_entry():
            entry = Entry()
            entry.add_lazy_fields('lazy_a', ['ab_field', 'a_field', 'a_fail'])
            entry.add_lazy_fields('lazy_b', ['ab_field', 'b_field', 'a_fail'])
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
