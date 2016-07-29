from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import os
import glob

import pytest

from flexget import plugin, plugins
from flexget.event import event, fire_event


@pytest.mark.chdir
class TestPluginApi(object):
    """
    Contains plugin api related tests
    """

    config = 'tasks: {}'

    def test_unknown_plugin(self):
        with pytest.raises(plugin.DependencyError):
            plugin.get_plugin_by_name('nonexisting_plugin')

    def test_no_dupes(self):
        plugin.load_plugins()

        assert plugin.PluginInfo.dupe_counter == 0, "Duplicate plugin names, see log"

    def test_load(self):
        plugin.load_plugins()
        plugin_path = os.path.dirname(plugins.__file__)
        plugin_modules = set(os.path.basename(i)
                             for k in ("/*.py", "/*/*.py")
                             for i in glob.glob(plugin_path + k))
        assert len(plugin_modules) >= 10, "Less than 10 plugin modules looks fishy"
        # Hmm, this test isn't good, because we have plugin modules that don't register a class (like cli ones)
        # and one module can load multiple plugins TODO: Maybe consider some replacement
        # assert len(plugin.plugins) >= len(plugin_modules) - 1, "Less plugins than plugin modules"

    def test_register_by_class(self, execute_task):
        class TestPlugin(object):
            pass

        class Oneword(object):
            pass

        class TestHTML(object):
            pass

        assert 'test_plugin' not in plugin.plugins

        @event('plugin.register')
        def rp():
            plugin.register(TestPlugin, api_ver=2)
            plugin.register(Oneword, api_ver=2)
            plugin.register(TestHTML, api_ver=2)

        # Call load_plugins again to register our new plugins
        plugin.load_plugins()
        assert 'test_plugin' in plugin.plugins
        assert 'oneword' in plugin.plugins
        assert 'test_html' in plugin.plugins


class TestExternalPluginLoading(object):
    _config = """
        tasks:
          ext_plugin:
            external_plugin: yes
    """

    @pytest.yield_fixture()
    def config(self, request):
        os.environ['FLEXGET_PLUGIN_PATH'] = request.fspath.dirpath().join('external_plugins').strpath
        plugin.load_plugins()
        # fire the config register event again so that task schema is rebuilt with new plugin
        fire_event('config.register')
        yield self._config
        del os.environ['FLEXGET_PLUGIN_PATH']

    def test_external_plugin_loading(self, execute_task):
        # TODO: This isn't working because calling load_plugins again doesn't cause the schema for tasks to regenerate
        task = execute_task('ext_plugin')
        assert task.find_entry(title='test entry'), 'External plugin did not create entry'
