# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, absolute_import
from tests import FlexGetBase
import os
import codecs


class TestConfig(FlexGetBase):
    __tmp__ = True
    __yaml__ = """
        tasks:
          Задание:
            mock:
              - {title: 'Test', url: 'http://localhost/foo'}
    """

    def setup(self):
        super(TestConfig, self).setup()
        self.config_file = os.path.join(self.__tmp__, 'config.yml')
        with codecs.open(self.config_file, 'w', 'utf8') as f:
            f.write(self.__yaml__)

    def test_config_checker_utf8(self):
        self.manager.pre_check_config(self.config_file)
