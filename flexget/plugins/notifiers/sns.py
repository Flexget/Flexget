from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import json
import logging

from flexget import plugin
from flexget.event import event

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
            'message': {'type': 'string', 'default': DEFAULT_TEMPLATE_VALUE},
            'aws_access_key_id': {'type': 'string'},
            'aws_secret_access_key': {'type': 'string'},
            'aws_region': {'type': 'string'},
            'profile_name': {'type': 'string'},
            'file_template': {'type': 'string', 'format': 'file_template'},
        },
        'required': ['title', 'aws_region'],
        'additionalProperties': False,
    }

    def notify(self, data):
        try:
            import boto3  # noqa
        except ImportError as e:
            log.debug("Error importing boto3: %s", e)
            raise plugin.DependencyError("sns", "boto3", "Boto3 module required. ImportError: %s" % e)

        session = boto3.Session(aws_access_key_id=data.get('aws_access_key_id'),
                                aws_secret_access_key=data.get('aws_secret_access_key'),
                                profile_name=data.get('profile_name'),
                                region_name=data['aws_region'])
        sns = session.resource('sns')
        topic = sns.Topic(data['title'])

        try:
            topic.publish(Message=data['message'])
        except Exception as e:
            log.error("Error publishing %s: ", e.args[0])
            return
        else:
            log.verbose('SNS notification sent')

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
