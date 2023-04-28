import jinja2
import pytest


class TestJinjaFilters:
    config = """
        tasks:
          stripyear:
            mock:
              - {"title":"The Matrix (1999)", "url":"mock://local1" }
              - {"title":"The Matrix", "url":"mock://local2" }
              - {"title":"The Matrix 1999", "url":"mock://local3" }
              - {"title":"2000", "url":"mock://local3" }
              - {"title":"2000 (2020)", "url":"mock://local4" }
              - {"title":"2000 2020", "url":"mock://local5" }
                
            accept_all: yes
                
            set:
              name: "{{title|strip_year}}"
              year: "{{title|get_year}}"
    """

    custom_filters = [
        'pathbase',
        'pathname',
        'pathext',
        'pathdir',
        'pathscrub',
        're_replace("a", "b")',
        're_search("a")',
        'formatdate("%Y")',
        'parsedate',
        'date_suffix',
        'format_number',
        'pad(5)',
        'to_date',
        'strip_year',
        'get_year',
        'parse_size',
        'asciify',
        'strip_symbols',
    ]

    def test_stripyear(self, execute_task):
        task = execute_task('stripyear')

        assert len(task.accepted) == 6
        assert task.accepted[0]['name'] == 'The Matrix'
        assert task.accepted[0]['year'] == 1999

        assert task.accepted[1]['name'] == 'The Matrix'
        assert task.accepted[1]['year'] is None

        assert task.accepted[2]['name'] == 'The Matrix'
        assert task.accepted[2]['year'] == 1999

        assert task.accepted[3]['name'] == 2000
        assert task.accepted[3]['year'] is None

        assert task.accepted[4]['name'] == 2000
        assert task.accepted[4]['year'] == 2020

        assert task.accepted[5]['name'] == 2000
        assert task.accepted[5]['year'] == 2020

    @pytest.mark.parametrize('test_filter', custom_filters)
    def test_undefined_preserved(self, test_filter):
        """
        Test that when an undefined field gets passed to one of our custom jinja filters that it stays undefined,
        instead of turning into some sort of other error. Covering up the undefined error makes it harder to figure
        out what went wrong with the template.
        """
        from flexget.utils.template import environment

        template = environment.from_string('{{non_existent_field|%s}}' % test_filter)
        with pytest.raises(jinja2.UndefinedError):
            template.render({})

    def test_all_custom_filters_tested(self):
        """Checks that all of our custom filters are in the list of filters to test."""
        from flexget.utils.template import environment

        filters = [f.split('(')[0] for f in self.custom_filters]
        for filter_name, filt in environment.filters.items():
            if not filt.__module__.startswith('flexget'):
                continue
            if filter_name in ('d', 'default'):
                # These aren't really custom, but we override them, so they show up in our module
                continue
            assert filter_name in filters
