from tests import FlexGetBase
from flexget import plugin
from nose.tools import raises


class TestPluginApi(object):
    """
    Contains plugin api related tests
    """

    @raises(plugin.DependencyError)
    def test_unknown_plugin(self):
        plugin.get_plugin_by_name('nonexisting_plugin')

    def test_register_by_class(self):

        class TestPlugin(object):
            pass

        class TestHTML(object):
            pass

        assert 'test_plugin' not in plugin.plugins
        plugin.register_plugin(TestPlugin)
        plugin.register_plugin(TestHTML)
        assert 'test_plugin' in plugin.plugins
        assert 'test_html' in plugin.plugins
