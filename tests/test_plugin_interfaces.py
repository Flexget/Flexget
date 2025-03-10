from flexget import plugin


class TestInterfaces:
    """Test that any plugins declaring certain interfaces at least superficially comply with those interfaces."""

    @staticmethod
    def get_plugins(interface):
        plugins = list(plugin.get_plugins(interface=interface))
        assert plugins, 'No plugins for this interface found.'
        return plugins

    def test_task_interface(self):
        for p in self.get_plugins('task'):
            assert isinstance(p.schema, dict), 'Task interface requires a schema to be defined.'
            assert p.phase_handlers, (
                'Task plugins should have at least on phase handler (on_task_X) method.'
            )

    def test_list_interface(self):
        for p in self.get_plugins('list'):
            assert isinstance(p.schema, dict), 'List interface requires a schema to be defined.'
            assert hasattr(p.instance, 'get_list'), (
                'List plugins must implement a get_list method.'
            )

    def test_search_interface(self):
        for p in self.get_plugins('search'):
            assert isinstance(p.schema, dict), 'Search interface requires a schema to be defined.'
            assert hasattr(p.instance, 'search'), 'Search plugins must implement a search method.'
