from unittest.mock import Mock, patch

import pytest

from flexget.plugins.output import sns
from flexget.task import Task


@pytest.mark.require_optional_deps
class TestNotifySNS:
    @patch('boto3.Session')
    def test_emitter_build_session_from_empty_config(self, session):
        e = sns.SNSNotificationEmitter({'aws_region': 'test'})
        e.build_session()
        assert e.session is session.return_value
        session.assert_called_once_with(
            region_name='test',
            aws_access_key_id=None,
            aws_secret_access_key=None,
            profile_name=None,
        )

    @patch('boto3.Session')
    def test_emitter_uses_config_credentials(self, session):
        e = sns.SNSNotificationEmitter(
            {
                'aws_region': None,
                'aws_access_key_id': 'DUMMY',
                'aws_secret_access_key': 'DUMMYKEY',
                'profile_name': 'profile-name',
            }
        )
        e.build_session()
        session.assert_called_once_with(
            region_name=None,
            aws_access_key_id='DUMMY',
            aws_secret_access_key='DUMMYKEY',
            profile_name='profile-name',
        )

    @patch('flexget.plugins.output.sns.SNSNotificationEmitter.get_topic')
    def test_dry_run_does_not_send_message(self, get_topic):
        topic = get_topic.return_value
        manager = Mock()
        manager.config = {'tasks': {}}
        task = Mock(wraps=Task(manager, 'fake'))
        task.options.test = True
        event = Mock()
        task.accepted = [event]

        e = sns.SNSNotificationEmitter({'aws_region': 'test', 'sns_topic_arn': 'arn'})
        e.send_notifications(task)

        event.render.assert_called_once_with(sns.DEFAULT_TEMPLATE_VALUE)
        assert not topic.publish.called

    @patch('flexget.plugins.output.sns.SNSNotificationEmitter.get_topic')
    def test_send_message_for_event(self, get_topic):
        topic = get_topic.return_value
        manager = Mock()
        manager.config = {'tasks': {}}
        task = Mock(wraps=Task(manager, 'fake'))
        task.options.test = False
        event = Mock()
        task.accepted = [event]

        e = sns.SNSNotificationEmitter({'aws_region': 'test', 'sns_topic_arn': 'arn'})
        e.send_notifications(task)
        topic.publish.assert_called_once_with(Message=event.render.return_value)
