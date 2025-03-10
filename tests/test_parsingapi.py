from flexget import plugin
from flexget.components.parsing import plugin_parsing


class TestParsingAPI:
    def test_all_types_handled(self):
        declared_types = set(plugin_parsing.PARSER_TYPES)
        method_handlers = {
            m[6:] for m in dir(plugin.get('parsing', 'tests')) if m.startswith('parse_')
        }
        assert set(declared_types) == set(method_handlers), (
            f'declared parser types: {declared_types}, handled types: {method_handlers}'
        )

    def test_parsing_plugins_have_parse_methods(self):
        for parser_type in plugin_parsing.PARSER_TYPES:
            for p in plugin.get_plugins(interface=f'{parser_type}_parser'):
                assert hasattr(p.instance, f'parse_{parser_type}'), (
                    f'{parser_type} parsing plugin {p.name} has no parse_{parser_type} method'
                )


class TestTaskParsing:
    config = """
        tasks:
          explicit_parser:
            parsing:
              movie: guessit
              series: guessit
    """

    def test_selected_parser_cleared(self, manager, execute_task):
        # make sure when a non-default parser is installed on a task, it doesn't affect other tasks
        execute_task('explicit_parser')
        assert not plugin_parsing.selected_parsers
