import json

from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='output.sns')

DEFAULT_TEMPLATE_VALUE = json.dumps(
    {
        'entry': {
            'title': '{{title}}',
            'url': '{{url}}',
            'original_url': '{{original_url}}',
            'series': '{{series_name}}',
            'series_id': '{{series_id}}',
        },
        'task': '{{task}}',
    }
)


class SNSNotification:
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
            'sns_notification_template': {'type': 'string', 'default': DEFAULT_TEMPLATE_VALUE},
            'aws_access_key_id': {'type': 'string'},
            'aws_secret_access_key': {'type': 'string'},
            'aws_region': {'type': 'string'},
            'profile_name': {'type': 'string'},
        },
        'required': ['sns_topic_arn', 'aws_region'],
        'additionalProperties': False,
    }

    def on_task_start(self, task, config):
        # verify that we actually support Boto 3
        try:
            import boto3  # noqa
        except ImportError as e:
            logger.debug('Error importing boto3: {}', e)
            raise plugin.DependencyError(
                "sns", "boto3", "Boto3 module required. ImportError: %s" % e
            )

    # this has to run near the end of the plugin chain, because we
    # should notify after all other outputs.
    @plugin.priority(0)
    def on_task_output(self, task, config):
        sender = SNSNotificationEmitter(config)
        sender.send_notifications(task)


class SNSNotificationEmitter:
    def __init__(self, config):
        self.config = config
        import boto3

        self.boto3 = boto3

        self.sns_notification_template = self.config.get(
            'sns_notification_template', DEFAULT_TEMPLATE_VALUE
        )

    def build_session(self):
        self.session = self.boto3.Session(
            aws_access_key_id=self.config.get('aws_access_key_id', None),
            aws_secret_access_key=self.config.get('aws_secret_access_key', None),
            profile_name=self.config.get('profile_name', None),
            region_name=self.config['aws_region'],
        )

    def get_topic(self):
        self.build_session()
        sns = self.session.resource('sns')
        topic = sns.Topic(self.config['sns_topic_arn'])
        return topic

    def send_notifications(self, task):
        topic = self.get_topic()

        for entry in task.accepted:
            message = entry.render(self.sns_notification_template)
            if task.options.test:
                logger.info(
                    'SNS publication: region={}, arn={}', self.config['aws_region'], topic.arn
                )
                logger.info('Message: {}', message)
                continue

            try:
                response = topic.publish(Message=message)
            except Exception as e:
                logger.error('Error publishing {}: {}', entry['title'], e)
                continue
            else:
                logger.debug('Published {}: {}', entry, response)


@event('plugin.register')
def register_sns_plugin():
    plugin.register(SNSNotification, 'sns', api_ver=2)
