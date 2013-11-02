# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, absolute_import
import os

from tests import FlexGetBase
from flexget.manager import Manager


class TestConfig(FlexGetBase):
    def setup(self):
        super(TestConfig, self).setup()
        # Replace config loading methods of MockManager with the real ones
        self.manager.find_config = Manager.find_config.__get__(self.manager, self.manager.__class__)
        self.manager.load_config = Manager.load_config.__get__(self.manager, self.manager.__class__)

    def test_config_find_load_and_check_utf8(self):
        config_utf8_filename = os.path.join(self.base_path, 'config_utf8.yml')
        self.manager.options.config = config_utf8_filename

        self.manager.config = {}
        self.manager.find_config()
        self.manager.load_config()
        assert self.manager.config, 'Config didn\'t load'
