from tests import FlexGetBase
from flexget.plugin import PluginDependencyError
from nose.tools import raises

class TestPluginApi(FlexGetBase):
    """
    Contains plugin api related tests
    """
    @raises(PluginDependencyError)
    def test_unknown_plugin(self):
        from flexget.plugin import get_plugin_by_name
        get_plugin_by_name('nonexisting_plugin')
