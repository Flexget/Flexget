import os
import glob
from flexget import plugin, plugins
from nose.tools import raises


class TestPluginApi(object):
    """
    Contains plugin api related tests
    """

    @raises(plugin.DependencyError)
    def test_unknown_plugin(self):
        plugin.get_plugin_by_name('nonexisting_plugin')

    def test_no_dupes(self):
        from flexget.options import CoreArgumentParser
        plugin.load_plugins(CoreArgumentParser())

        assert plugin.PluginInfo.dupe_counter == 0, "Duplicate plugin names, see log"

    def test_load(self):
        from flexget.options import CoreArgumentParser

        plugin.load_plugins(CoreArgumentParser())
        assert 0 == plugin.load_plugins(CoreArgumentParser())
        plugin_path = os.path.dirname(plugins.__file__)
        plugin_modules = set(os.path.basename(i)
            for k in ("/*.py", "/*/*.py")
            for i in glob.glob(plugin_path + k))
        assert len(plugin_modules) >= 10, "Less than 10 plugin modules looks fishy"
        assert len(plugin.plugins) >= len(plugin_modules) - 1, "Less plugins than plugin modules"

    def test_register_by_class(self):

        class TestPlugin(object):
            pass

        class Oneword(object):
            pass

        class TestHTML(object):
            pass

        assert 'test_plugin' not in plugin.plugins
        plugin.register_plugin(TestPlugin)
        plugin.register_plugin(Oneword)
        plugin.register_plugin(TestHTML)
        assert 'test_plugin' in plugin.plugins
        assert 'oneword' in plugin.plugins
        assert 'test_html' in plugin.plugins
