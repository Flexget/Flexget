# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase
from flexget.manager import Manager
import os


class TestConfig(FlexGetBase):
    def setup(self):
        super(TestConfig, self).setup()
        # save original and revert find_config method for tests
        self.origin_find_config = self.manager.__class__.find_config
        self.manager.__class__.find_config = Manager.find_config

    def teardown(self):
        # restore original mock method
        self.manager.__class__.find_config = self.origin_find_config
        super(TestConfig, self).teardown()

    def test_config_find_load_and_check_utf8(self):
        config_utf8_filename = os.path.join(self.base_path, 'config_utf8.yml')
        self.manager.options.config = config_utf8_filename

        self.manager.config = {}
        self.manager.find_config()
        assert self.manager.config, 'Config didn\'t load'
