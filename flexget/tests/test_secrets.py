from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import pytest

from flexget.event import fire_event
from flexget.manager import Session
from flexget.plugins.modify.config_secrets import Secrets


@pytest.mark.usefixtures('tmpdir')
class TestSecretsFromFile(object):
    config = """
        secrets: __tmp__/secret.yml
        tasks:
          test_secret_from_file:
            mock:
              - { title: 'test', location: 'http://mock'}
            if:
              - '{{ secrets.test_secret }}': accept

    """

    @pytest.mark.filecopy('secret.yml', '__tmp__/secret.yml')
    def test_secret_from_file(self, execute_task, manager):
        task = execute_task('test_secret_from_file')
        assert len(task.accepted) == 1


class TestSecretsFromDB(object):
    config = """
        secrets: yes
        tasks:
          test_secret_from_db:
            mock:
              - { title: 'test', location: 'http://mock'}
            if:
              - '{{ secrets.test_secret_db }}': accept

    """

    def test_secret_from_db(self, execute_task, manager):
        with Session() as session:
            s = Secrets(secrets={'test_secret_db': True})
            session.add(s)

        fire_event('manager.before_config_validate', manager.config, manager)

        task = execute_task('test_secret_from_db')
        assert len(task.accepted) == 1


