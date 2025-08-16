from loguru import logger
from requests.exceptions import RequestException

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginWarning
from flexget.utils.requests import Session as RequestSession

requests = RequestSession(max_retries=3)

plugin_name = 'slack'

logger = logger.bind(name=plugin_name)


class SlackNotifier:
    """Send a Slack notification.

    `Sending messages using incoming webhooks <https://api.slack.com/messaging/webhooks>`__

    Example::

      notify:
        entries:
          via:
            - slack:
                web_hook_url: "https://hooks.slack.com/services/..."
                blocks:
                  - section:
                      text: '<{{ tvdb_url }}|{{ series_name }} ({{ series_id }})>'
                  - section:
                      text: '{{ tvdb_ep_overview }}'
                      image:
                        url: "https://api.slack.com/img/blocks/bkb_template_images/plants.png"
                        alt_text: 'plants'
                      fields:
                        - '*Score*'
                        - '*Genres*'
                        - '{{ imdb_score }}'
                        - "{{ imdb_genres | join(', ') | title }}"
                        - '*Rating*'
                        - '*Cast*'
                        - '{{ imdb_mpaa_rating }}'
                        - >
                          {% for key, value in imdb_actors.items() %}{{ value }}{% if not loop.last %}, {% endif %}
                          {% endfor %}
                  - image:
                      url: "{{ tvdb_banner }}"
                      alt_text: "{{ series_name }} Banner"
                  - context:
                      - image:
                          url: 'https://image.freepik.com/free-photo/red-drawing-pin_1156-445.jpg'
                          alt_text: 'red pin'
                      - text: ':round_pushpin:'
                      - text: 'Task: {{ task }}'

    `Legacy custom integrations incoming webhooks <https://api.slack.com/legacy/custom-integrations/messaging/webhooks>`__

    Example (legacy)::

      notify:
        entries:
          via:
            - slack:
                web_hook_url: <string>
                [channel: <string>] (override channel, use "@username" or "#channel")
                [username: <string>] (override username)
                [icon_emoji: <string>] (override emoji icon)
                [icon_url: <string>] (override emoji icon)
                [attachments: <array>[<object>]] (override attachments)
    """

    schema = {
        'definitions': {
            'image_block': {
                'type': 'object',
                'properties': {
                    'url': {'type': 'string', 'format': 'uri'},
                    'alt_text': {'type': 'string'},
                },
                'required': ['url', 'alt_text'],
                'additionalProperties': False,
            },
            'image_block_w_title': {
                'type': 'object',
                'properties': {
                    'url': {'type': 'string', 'format': 'uri'},
                    'title': {'type': 'string'},
                    'alt_text': {'type': 'string'},
                },
                'required': ['url', 'alt_text'],
                'additionalProperties': False,
            },
        },
        'type': 'object',
        'properties': {
            'web_hook_url': {'type': 'string', 'format': 'uri'},
            'username': {'type': 'string', 'default': 'Flexget'},
            'icon_url': {'type': 'string', 'format': 'uri'},
            'icon_emoji': {'type': 'string'},
            'channel': {'type': 'string'},
            'unfurl_links': {'type': 'boolean'},
            'message': {'type': 'string'},
            'attachments': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'title': {'type': 'string'},
                        'author_name': {'type': 'string'},
                        'author_link': {'type': 'string'},
                        'author_icon': {'type': 'string'},
                        'title_link': {'type': 'string'},
                        'image_url': {'type': 'string'},
                        'thumb_url': {'type': 'string'},
                        'footer': {'type': 'string'},
                        'footer_icon': {'type': 'string'},
                        'ts': {'type': 'number'},
                        'fallback': {'type': 'string'},
                        'text': {'type': 'string'},
                        'pretext': {'type': 'string'},
                        'color': {'type': 'string'},
                        'fields': {
                            'type': 'array',
                            'minItems': 1,
                            'items': {
                                'type': 'object',
                                'properties': {
                                    'title': {'type': 'string'},
                                    'value': {'type': 'string'},
                                    'short': {'type': 'boolean'},
                                },
                                'required': ['title'],
                                'additionalProperties': False,
                            },
                        },
                        'actions': {
                            'type': 'array',
                            'minItems': 1,
                            'items': {
                                'type': 'object',
                                'properties': {
                                    'name': {'type': 'string'},
                                    'text': {'type': 'string'},
                                    'type': {'type': 'string'},
                                    'value': {'type': 'string'},
                                },
                                'required': ['name', 'text', 'type', 'value'],
                                'additionalProperties': False,
                            },
                        },
                        'callback_id': {'type': 'string'},
                    },
                    'required': ['fallback'],
                    'dependentRequired': {'actions': ['callback_id']},
                    'additionalProperties': False,
                },
            },
            'blocks': {
                'type': 'array',
                'minItems': 1,
                'maxItems': 50,
                'items': {
                    'type': 'object',
                    'properties': {
                        'section': {
                            'type': 'object',
                            'properties': {
                                'text': {'type': 'string'},
                                'image': {'$ref': '#/definitions/image_block'},
                                'fields': {
                                    'type': 'array',
                                    'minItems': 1,
                                    'maxItems': 10,
                                    'items': {'type': 'string'},
                                },
                            },
                            'anyOf': [{'required': ['text']}, {'required': ['fields']}],
                            'additionalProperties': False,
                        },
                        'image': {
                            'type': 'object',
                            'properties': {
                                'text': {'type': 'string'},
                                'image': {'$ref': '#/definitions/image_block_w_title'},
                            },
                        },
                        'context': {
                            'type': 'array',
                            'minItems': 1,
                            'maxItems': 10,
                            'items': {
                                'type': 'object',
                                'properties': {
                                    'text': {'type': 'string'},
                                    'image': {'$ref': '#/definitions/image_block'},
                                },
                                'anyOf': [
                                    {'required': ['text']},
                                    {'required': ['image']},
                                ],
                            },
                        },
                        'divider': {'type': 'boolean'},
                    },
                    'additionalProperties': False,
                },
            },
        },
        'allOf': [
            {
                'if': {'required': ['blocks']},
                'then': {
                    'allOf': [
                        {
                            'not': {'required': ['message']},
                            'error_not': "Cannot specify 'message' while using version 2 Slack formatting",
                        },
                        {
                            'not': {'required': ['attachments']},
                            'error_not': "Cannot specify 'attachments' while using version 2 Slack formatting",
                        },
                    ],
                },
                'else': {
                    'anyOf': [{'required': ['message']}, {'required': ['attachments']}],
                    'allOf': [
                        {
                            'not': {'required': ['icon_emoji', 'icon_url']},
                            'error_not': "Can only use one of 'icon_emoji' or 'icon_url'",
                        },
                        {
                            'not': {'required': ['blocks']},
                            'error_not': "Cannot specify 'blocks' while using version 1 Slack formatting",
                        },
                    ],
                },
            }
        ],
        'required': ['web_hook_url'],
        'additionalProperties': False,
    }

    def notify(self, title, message, config):
        """Send a Slack notification."""
        # version 2 Block Kit formatting
        if config.get('blocks'):
            """
                        Using the Block Kit Builder can help preview how your configuration will be displayed:
                        https://api.slack.com/tools/block-kit-builder?mode=message
                        """
            notification = {'blocks': []}

            for block in config.get('blocks'):
                if block.get('section'):
                    logger.trace('section block')
                    section = {
                        'type': 'section',
                        'text': {
                            'type': 'mrkdwn',
                            'text': block['section']['text'],
                        },
                    }

                    if block['section'].get('image', {}).get('url'):
                        section['accessory'] = {
                            'type': 'image',
                            'image_url': block['section']['image']['url'],
                            'alt_text': block['section']['image']['alt_text'],
                        }

                    if block['section'].get('fields'):
                        section['fields'] = []

                        for field in block['section'].get('fields'):
                            section['fields'].append({'type': 'mrkdwn', 'text': field})

                    notification['blocks'].append(section)

                elif block.get('image'):
                    logger.trace('image block')
                    image = {
                        'type': 'image',
                        'image_url': block['image']['url'],
                        'alt_text': block['image']['alt_text'],
                    }

                    if block['image'].get('title'):
                        image['title'] = {
                            'type': 'plain_text',
                            'text': block['image']['title'],
                            'emoji': True,
                        }

                    notification['blocks'].append(image)

                elif block.get('context'):
                    logger.trace('context block')
                    context = {'type': 'context', 'elements': []}

                    for block_context in block.get('context'):
                        if block_context.get('text'):
                            context['elements'].append({
                                'type': 'mrkdwn',
                                'text': block_context['text'],
                            })

                        elif block_context.get('image'):
                            context['elements'].append({
                                'type': 'image',
                                'image_url': block_context['image']['url'],
                                'alt_text': block_context['image']['alt_text'],
                            })

                    notification['blocks'].append(context)

                elif block.get('divider'):
                    logger.trace('divider block')
                    notification['blocks'].append({'type': 'divider'})

        # version 1 is the Legacy formatting
        else:
            # username, channel, icon_emoji, and icon_url are deprecated and ignored by the Slack API,
            # therefore they've been removed from the posted data
            notification = {
                'text': message,
                'username': config.get('username'),
                'channel': config.get('channel'),
                'attachments': config.get('attachments'),
            }
            if config.get('icon_emoji'):
                notification['icon_emoji'] = f':{config["icon_emoji"].strip(":")}:'
            if config.get('icon_url'):
                notification['icon_url'] = config['icon_url']

        try:
            requests.post(config['web_hook_url'], json=notification)
        except RequestException as e:
            raise PluginWarning(e.args[0])


@event('plugin.register')
def register_plugin():
    plugin.register(SlackNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])
