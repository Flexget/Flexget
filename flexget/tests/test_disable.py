from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import pytest


class PluginFakeUrlrewriter(object):
    URL = "fake://url.com"

    def url_rewritable(self, task, entry):
        if entry['url'] != self.URL:
            return True

    def url_rewrite(self, task, entry):
        entry['url'] = self.URL


class TestDisable(object):
    config = """
        tasks:
          disable_from_config:
            mock:
              - title: entry 1
          disable_builtins:
            mock:
              - title: entry 1
            accept_all: yes
          disable_urlrewriter:
            mock:
              - title: entry 1
                url: blah://aoeu
            accept_all: yes
            disable: [seen]
        """

    def test_disable_config_plugin(self, execute_task, manager):
        task = execute_task('disable_from_config')
        assert len(task.entries) == 1
        manager.config["tasks"]["disable_from_config"]["disable"] = ["mock"]
        task = execute_task('disable_from_config')
        assert len(task.entries) == 0

    def test_disable_builtins(self, execute_task, manager):
        task = execute_task('disable_builtins')
        assert len(task.accepted) == 1
        task = execute_task('disable_builtins')
        assert len(task.accepted) == 0
        # Make sure builtins special command works
        manager.config["tasks"]["disable_builtins"]["disable"] = ["builtins"]
        task = execute_task('disable_builtins')
        assert len(task.accepted) == 1, "seen builtin should have been disabled with 'builtins' keyword"
        # Make sure builtins are also disabled with their specific name
        manager.config["tasks"]["disable_builtins"]["disable"] = ["seen"]
        assert len(task.accepted) == 1, "seen builtin should have been disabled"

    @pytest.mark.register_plugin(PluginFakeUrlrewriter, 'fake_urlrewriter', interfaces=['urlrewriter'], api_ver=2)
    def test_disable_urlrewriter(self, execute_task, manager):
        task = execute_task('disable_urlrewriter')
        assert task.accepted[0]['url'] == PluginFakeUrlrewriter.URL
        manager.config["tasks"]["disable_urlrewriter"]["disable"] = ["seen", "fake_urlrewriter"]
        task = execute_task('disable_urlrewriter')
        assert task.accepted[0]['url'] == "blah://aoeu"
