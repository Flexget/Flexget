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
          parse_size:
            mock:
              - {"title": "The Matrix [13.84GB]", "actual": 13.84 }
              - {"title": "The Matrix [13.84 GB]", "actual": 13.84 }
              - {"title": "The Matrix [13.84 GiB]", "actual": 13.84 }
              - {"title": "The Matrix [13 GB]", "actual": 13 }
              - {"title": "The Matrix [WebRip 6mbps][13.84GB]", "actual": 13.84 }

            accept_all: yes

            set:
              size: "{{title|parse_size}}"
              size_si: "{{title|parse_size(si=True)}}"
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
        'format_size',
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

    def test_parse_size(self, execute_task):
        task = execute_task('parse_size')

        assert len(task.accepted) == 5

        assert task.accepted[0]['size'] == int(task.accepted[0]['actual'] * 1024**3)
        assert task.accepted[0]['size_si'] == int(task.accepted[0]['actual'] * 1000**3)

        assert task.accepted[1]['size'] == int(task.accepted[1]['actual'] * 1024**3)
        assert task.accepted[1]['size_si'] == int(task.accepted[1]['actual'] * 1000**3)

        assert task.accepted[2]['size'] == int(task.accepted[2]['actual'] * 1024**3)
        # GiB is always 1024 based
        assert task.accepted[2]['size_si'] == int(task.accepted[2]['actual'] * 1024**3)

        assert task.accepted[3]['size'] == int(task.accepted[3]['actual'] * 1024**3)
        assert task.accepted[3]['size_si'] == int(task.accepted[3]['actual'] * 1000**3)

        assert task.accepted[4]['size'] == int(task.accepted[4]['actual'] * 1024**3)
        assert task.accepted[4]['size_si'] == int(task.accepted[4]['actual'] * 1000**3)

    @pytest.mark.parametrize('test_filter', custom_filters)
    def test_undefined_preserved(self, test_filter):
        """Test that when an undefined field gets passed to one of our custom jinja filters that it stays undefined, instead of turning into some sort of other error.

        Covering up the undefined error makes it harder to figure
        out what went wrong with the template.
        """
        from flexget.utils.template import environment

        template = environment.from_string(f'{{{{non_existent_field|{test_filter}}}}}')
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
