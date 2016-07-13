from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import pytest


@pytest.mark.usefixtures('tmpdir')
class TestSecrets(object):
    config = """
        secrets: __tmp__/secret.yml
        tasks:
          test_secret:
            mock:
              - { title: 'test', location: 'http://mock'}
            if:
              - '{{ secrets.test_secret }}': accept
    """

    @pytest.mark.filecopy('secret.yml', '__tmp__/secret.yml')
    def test_secret_from_file(self, execute_task):
        task = execute_task('test_secret')
        assert len(task.accepted) == 1
