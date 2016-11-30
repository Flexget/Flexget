from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import json
import logging

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginWarning

__name__ = 'sns'

log = logging.getLogger(__name__)

DEFAULT_TEMPLATE_VALUE = json.dumps({
    'entry': {
        'title': '{{title}}',
        'url': '{{url}}',
        'original_url': '{{original_url}}',
        'series': '{{series_name}}',
        'series_id': '{{series_id}}',
    },
    'task': '{{task_name}}'
})


class SNSNotifier(object):
    """
    Emits SNS notifications of entries

    Optionally writes the torrent itself to S3

    Example configuration::

      sns:
        [aws_access_key_id: <AWS ACCESS KEY ID>] (will be taken from AWS_ACCESS_KEY_ID environment if not provided)
        [aws_secret_access_key: <AWS SECRET ACCESS KEY>] (will be taken from AWS_SECRET_ACCESS_KEY environment if
            not provided)
        [profile_name: <AWS PROFILE NAME>] (If provided, use this profile name instead of the default.)
        aws_region: <REGION>
        sns_topic_arn: <SNS ARN>
        [sns_notification_template: <TEMPLATE] (defaults to DEFAULT_TEMPLATE_VALUE)

    """

    schema = {
        'type': 'object',
        'properties': {
            'title': {'type': 'string'},
            'sns_topic_arn': {'type': 'string'},
            'message': {'type': 'string'},
            'aws_access_key_id': {'type': 'string'},
            'aws_secret_access_key': {'type': 'string'},
            'aws_region': {'type': 'string'},
            'profile_name': {'type': 'string'},
            'file_template': {'type': 'string'},
        },
        'required': ['sns_topic_arn', 'aws_region'],
        'additionalProperties': False,
    }

    def notify(self, sns_topic_arn, title, message, url, aws_region, aws_access_key_id=None, aws_secret_access_key=None,
               profile_name=None, **kwargs):
        """
        Send an Amazon SNS notification

        :param str sns_topic_arn: SNS Topic ARN
        :param str title: Notification title
        :param str message: Notification message
        :param str aws_region: AWS region
        :param str aws_access_key_id: AWS access key ID. Will be taken from AWS_ACCESS_KEY_ID environment if not
            provided.
        :param str aws_secret_access_key: AWS secret access key ID. Will be taken from AWS_SECRET_ACCESS_KEY
            environment if not provided.
        :param str profile_name: If provided, use this profile name instead of the default.
        """
        try:
            import boto3  # noqa
        except ImportError as e:
            log.debug("Error importing boto3: %s", e)
            raise plugin.DependencyError("sns", "boto3", "Boto3 module required. ImportError: %s" % e)

        session = boto3.Session(aws_access_key_id=aws_access_key_id,
                                aws_secret_access_key=aws_secret_access_key,
                                profile_name=profile_name,
                                region_name=aws_region)
        sns = session.resource('sns')
        topic = sns.Topic(title)
        sns_message = json.dumps({
            'entry': {
                'title': title,
                'url': url,
            }
        })
        try:
            topic.publish(Message=sns_message)
        except Exception as e:
            raise PluginWarning("Error publishing %s: " % e.args[0])

    # Run last to make sure other outputs are successful before sending notification
    @plugin.priority(0)
    def on_task_output(self, task, config):
        # Send default values for backwards compatibility
        notify_config = {
            'to': [{__name__: config}],
            'scope': 'entries',
            'what': 'accepted'
        }
        plugin.get_plugin_by_name('notify').instance.send_notification(task, notify_config)


@event('plugin.register')
def register_sns_plugin():
    plugin.register(SNSNotifier, __name__, api_ver=2, groups=['notifiers'])
