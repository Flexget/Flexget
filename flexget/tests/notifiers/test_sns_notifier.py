from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from mock import patch

from flexget.plugins.notifiers import sns


class TestNotifySNS(object):
    @patch('boto3.Session')
    def test_emitter_build_session_from_empty_config(self, Session):
        sns.SNSNotifier().notify(aws_region='test', title='test', message='test')
        Session.assert_called_once_with(
            region_name='test',
            aws_access_key_id=None,
            aws_secret_access_key=None,
            profile_name=None,
        )

    @patch('boto3.Session')
    def test_emitter_uses_config_credentials(self, Session):
        sns.SNSNotifier().notify(aws_region=None, aws_access_key_id='DUMMY', aws_secret_access_key='DUMMYKEY',
                                 profile_name='profile-name', title='test', message='test')
        Session.assert_called_once_with(
            region_name=None,
            aws_access_key_id='DUMMY',
            aws_secret_access_key='DUMMYKEY',
            profile_name='profile-name',
        )
