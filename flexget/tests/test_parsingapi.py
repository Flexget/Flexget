from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from flexget.plugin import get_plugin_by_name, get_plugins
from flexget.plugins.parsers import plugin_parsing


class TestParsingAPI(object):
    def test_all_types_handled(self):
        declared_types = set(plugin_parsing.PARSER_TYPES)
        method_handlers = set(m[6:] for m in dir(get_plugin_by_name('parsing').instance) if m.startswith('parse_'))
        assert set(declared_types) == set(method_handlers), \
            'declared parser types: %s, handled types: %s' % (declared_types, method_handlers)

    def test_parsing_plugins_have_parse_methods(self):
        for parser_type in plugin_parsing.PARSER_TYPES:
            for plugin in get_plugins(interface='%s_parser' % parser_type):
                assert hasattr(plugin.instance, 'parse_%s' % parser_type), \
                    '{type} parsing plugin {name} has no parse_{type} method'.format(type=parser_type, name=plugin.name)


class TestTaskParsing(object):
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
