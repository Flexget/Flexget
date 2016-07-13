from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

from mock import patch

from flexget.plugins.modify import config_secrets


class TestSecrets(object):
    config = """
        secrets: test_secret.yml
        tasks:
          test_secret:
            mock:
              - { title: 'test', location: 'http://mock'}
            if:
              - '{{ secrets.test_secret }}': accept
    """

    @patch.object(config_secrets, 'secrets_from_file')
    def test_secret_from_file(self, mock_secret_file, execute_task):
        mock_secret_file.return_value = {'test_secret': True}

        task = execute_task('test_secret')
        assert mock_secret_file.called
        assert len(task.accepted) == 1
