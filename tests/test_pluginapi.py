from flexget.plugin import DependencyError
from nose.tools import raises


class TestPluginApi(object):
    """
    Contains plugin api related tests
    """

    @raises(DependencyError)
    def test_unknown_plugin(self):
        from flexget.plugin import get_plugin_by_name
        get_plugin_by_name('nonexisting_plugin')
