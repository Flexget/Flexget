from datetime import datetime

from dateutil.parser import ParserError, isoparse
from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginWarning
from flexget.utils.requests import RequestException, Session, TimedLimiter

plugin_name = 'discord'

logger = logger.bind(name=plugin_name)
session = Session()
session.add_domain_limiter(TimedLimiter('discord.com', '3 seconds'))


class DiscordNotifier:
    """
    Example::

      notify:
        entries:
          via:
            - discord:
                web_hook_url: <string>
                [username: <string>] (override the default username of the webhook)
                [avatar_url: <string>] (override the default avatar of the webhook)
                [embeds: <arrays>[<object>]] (override embeds)
    """

    schema = {
        'type': 'object',
        'properties': {
            'web_hook_url': {'type': 'string', 'format': 'uri'},
            'username': {'type': 'string', 'default': 'Flexget'},
            'avatar_url': {'type': 'string', 'format': 'uri'},
            'embeds': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'title': {'type': 'string'},
                        'description': {'type': 'string'},
                        'url': {'type': 'string', 'format': 'uri'},
                        'color': {'type': 'integer'},
                        'footer': {
                            'type': 'object',
                            'properties': {
                                'text': {'type': 'string'},
                                'icon_url': {'type': 'string', 'format': 'uri'},
                                'proxy_icon_url': {'type': 'string', 'format': 'uri'},
                            },
                            'required': ['text'],
                            'additionalProperties': False,
                        },
                        'image': {
                            'type': 'object',
                            'properties': {
                                'url': {'type': 'string', 'format': 'uri'},
                                'proxy_url': {'type': 'string', 'format': 'uri'},
                            },
                            'additionalProperties': False,
                        },
                        'thumbnail': {
                            'type': 'object',
                            'properties': {
                                'url': {'type': 'string', 'format': 'uri'},
                                'proxy_url': {'type': 'string', 'format': 'uri'},
                            },
                            'additionalProperties': False,
                        },
                        'timestamp': {'type': 'string'},
                        'provider': {
                            'type': 'object',
                            'properties': {
                                'name': {'type': 'string'},
                                'url': {'type': 'string', 'format': 'uri'},
                            },
                            'additionalProperties': False,
                        },
                        'author': {
                            'type': 'object',
                            'properties': {
                                'name': {'type': 'string'},
                                'url': {'type': 'string', 'format': 'uri'},
                                'icon_url': {'type': 'string', 'format': 'uri'},
                                'proxy_icon_url': {'type': 'string', 'format': 'uri'},
                            },
                            'additionalProperties': False,
                        },
                        'fields': {
                            'type': 'array',
                            'minItems': 1,
                            'items': {
                                'type': 'object',
                                'properties': {
                                    'name': {'type': 'string'},
                                    'value': {'type': 'string'},
                                    'inline': {'type': 'boolean'},
                                },
                                'required': ['name', 'value'],
                                'additionalProperties': False,
                            },
                        },
                    },
                    'additionalProperties': False,
                },
            },
        },
        'required': ['web_hook_url'],
        'additionalProperties': False,
    }

    def notify(self, title, message, config):
        """
        Send discord notification

        :param str message: message body
        :param dict config: discord plugin config
        """

        for embed in config.get('embeds', []):
            ts = embed.get('timestamp')
            if ts:
                if isinstance(ts, str):
                    if ts.isdigit():
                        try:
                            ts = datetime.utcfromtimestamp(int(ts))
                        except (ValueError, OverflowError):
                            logger.info(
                                f"Value provided for 'timestamp' ({embed['timestamp']}) "
                                f"is not a timestamp ({int(datetime.now().timestamp())})."
                            )
                    else:
                        try:
                            ts = isoparse(ts)
                            embed['timestamp'] = ts
                        except (ParserError, ValueError) as e:
                            logger.info(f"'timestamp' is in an invalid format: {e}")
                if not isinstance(ts, datetime):
                    embed.pop('timestamp', None)
                    logger.warning("'timestamp' is invalid, dropping it")
                else:
                    embed['timestamp'] = datetime.strftime(ts, r'%Y-%m-%dT%H:%M:%S%z')

        web_hook = {
            'content': message,
            'username': config.get('username'),
            'avatar_url': config.get('avatar_url'),
            'embeds': config.get('embeds'),
        }

        try:
            session.post(config['web_hook_url'], json=web_hook)
        except RequestException as e:
            raise PluginWarning(e.args[0])


@event('plugin.register')
def register_plugin():
    plugin.register(DiscordNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])
