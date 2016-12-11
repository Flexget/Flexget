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
            'sns_topic_arn': {'type': 'string'},
            'aws_access_key_id': {'type': 'string'},
            'aws_secret_access_key': {'type': 'string'},
            'aws_region': {'type': 'string'},
            'profile_name': {'type': 'string'},
            'url': {'type': 'string'}
        },
        'required': ['sns_topic_arn', 'aws_region'],
        'additionalProperties': False,
    }

    def notify(self, title, message, config):
        """
        Send an Amazon SNS notification
        """
        try:
            import boto3  # noqa
        except ImportError as e:
            log.debug("Error importing boto3: %s", e)
            raise plugin.DependencyError("sns", "boto3", "Boto3 module required. ImportError: %s" % e)

        session = boto3.Session(aws_access_key_id=config.get('aws_access_key_id'),
                                aws_secret_access_key=config.get('aws_secret_access_key'),
                                profile_name=config.get('profile_name'),
                                region_name=config['aws_region'])
        sns = session.resource('sns')
        topic = sns.Topic(config['sns_topic_arn'])
        # TODO: This is ignoring notification framework message and generating own?
        # Maybe it should remain regular output plugin.
        sns_message = json.dumps({
            'entry': {
                'title': title,
                'url': config.get('url'),
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
