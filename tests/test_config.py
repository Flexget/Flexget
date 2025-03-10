import os

import pytest

from flexget.manager import Manager

config_utf8 = os.path.join(os.path.dirname(__file__), 'config_utf8.yml')


class TestConfig:
    config = 'tasks: {}'

    @pytest.fixture
    def manager(self, manager):
        # Replace config loading methods of MockManager with the real ones
        manager._init_config = Manager._init_config.__get__(manager, manager.__class__)
        manager.load_config = Manager.load_config.__get__(manager, manager.__class__)
        return manager

    def test_config_find_load_and_check_utf8(self, manager, execute_task):
        manager.options.config = config_utf8

        manager.config = {}
        manager._init_config()
        manager.load_config()
        assert manager.config, 'Config didn\'t load'
