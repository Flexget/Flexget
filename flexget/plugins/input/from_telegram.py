"""Plugin for telegram input"""
import re

from loguru import logger
from requests.exceptions import HTTPError, RequestException

from flexget.config_schema import one_or_more
from flexget import plugin
from flexget.entry import Entry
from flexget.event import event

logger = logger.bind(name='from_telegram')

_TELEGRAM_API_URL = "https://api.telegram.org/"


class TelegramInput:
    """
    Parse any messages from Telegram and fills fields with regex

    Example:
      token: <token>
      only_new: yes
      whitelist:
        - username: <my_username>
        - group: <my_group>
        - fullname:
            first: <my_first_name>
            sur: <my_surname>
      entry:
        <field>: <regexp to match value>

    Note: If not declared, title will be the message
    """

    schema = {
        'type': 'object',
        'properties': {
            'token': {'type': 'string'},
            'types': one_or_more({'type': 'string', 'enum': ['private', 'group']}),
            'whitelist': {
                'type': 'array',
                'minItems': 1,
                'items': {
                    'oneOf': [
                        {
                            'type': 'object',
                            'properties': {'username': {'type': 'string'}},
                            'required': ['username'],
                            'additionalProperties': False,
                        },
                        {
                            'type': 'object',
                            'properties': {
                                'fullname': {
                                    'type': 'object',
                                    'properties': {
                                        'first': {'type': 'string'},
                                        'sur': {'type': 'string'},
                                    },
                                    'required': ['first', 'sur'],
                                    'additionalProperties': False,
                                }
                            },
                            'required': ['fullname'],
                            'additionalProperties': False,
                        },
                        {
                            'type': 'object',
                            'properties': {'group': {'type': 'string'}},
                            'required': ['group'],
                            'additionalProperties': False,
                        },
                    ]
                },
            },
            'only_new': {'type': 'boolean', 'default': True},
            'entry': {
                'type': 'object',
                'properties': {
                    'url': {'type': 'string', 'format': 'regex'},
                    'title': {'type': 'string', 'format': 'regex'},
                },
                'additionalProperties': {'type': 'string', 'format': 'regex'},
            },
        },
        'required': ['token'],
        'additonalProperties': False,
    }

    @plugin.internet(logger)
    def on_task_input(self, task, config):
        # Load The Configs
        token = config['token']
        only_new = config['only_new']
        entry_config = config.get('entry')
        whitelist = config.get('whitelist', [])
        types = config.get('types', ['private', 'group'])

        # Get Last Checked ID
        persistence_name = f"{token}_update_id"
        update_id = task.simple_persistence.get(persistence_name)

        # Get only new messages
        params = {}
        if update_id and only_new:
            update_id += 1
            params['offset'] = update_id

        # The Target URL
        url = f"{_TELEGRAM_API_URL}bot{token}/getUpdates"

        # Get Telegram Updates
        try:
            response = task.requests.get(url, timeout=60, raise_status=True, params=params).json()
        except HTTPError as e:
            raise plugin.PluginError(f"Error getting telegram update: {e}")

        # We have a error
        if not response['ok']:
            raise plugin.PluginError(
                f"Telegram updater returned error {response['error_code']}: {response['description']}"
            )

        # Get All New Messages
        messages = response['result']

        entries = []
        for message in messages:
            # This is the ID
            update_id = message['update_id']

            # Update the last ID for the Bot
            logger.debug("Last Update set to {}", update_id)
            task.simple_persistence[persistence_name] = update_id

            # We Don't care if it's not a message or no text
            if (
                'message' not in message
                or 'text' not in message['message']
                or 'chat' not in message['message']
                or 'type' not in message['message']['chat']
            ):
                logger.debug("Invalid message discarted: {}", message)
                continue

            logger.debug("Income message: {}", message)

            # Check Types
            if types and message['message']['chat']['type'] not in types:
                logger.debug("Ignoring message because of invalid type {}", message)
                continue

            # Create Base Entry
            text = message['message']['text']
            entry = Entry()
            entry['title'] = text

            # We need a url, so we add a dummy
            entry['url'] = f"http://localhost?update_id={str(update_id)}"

            # Store the message if we need to use it in other plugins
            entry['telegram_message'] = message['message']

            # Check From
            message_from = message['message']['from']
            message_chat = message['message']['chat']

            if whitelist:
                for check in whitelist:
                    if 'username' in check and check['username'] == message_from['username']:
                        logger.debug("WhiteListing: Username {}", message_from['username'])
                        break
                    elif (
                        'fullname' in check
                        and check['fullname']['first'] == message_from['first_name']
                        and check['fullname']['sur'] == message_from['last_name']
                    ):
                        logger.debug(
                            "WhiteListing: Full Name {} {}",
                            message_from['first_name'],
                            message_from['last_name'],
                        )
                        break
                    elif 'group' in check:
                        if (
                            message_chat['type'] == 'group'
                            and message_chat['title'] == check['group']
                        ):
                            logger.debug("WhiteListing: Group {}", message_chat['title'])
                            break
                else:
                    logger.debug("Ignoring message because of no whitelist match {}", message)
                    continue

            # Process the entry config
            accept = True
            if entry_config:
                for field, regexp in entry_config.items():
                    match = re.search(regexp, text)
                    if match:
                        try:
                            # Add field to entry
                            entry[field] = match.group(1)
                        except IndexError:
                            logger.error(
                                'Regex for field `{}` must contain a capture group', field
                            )
                            raise plugin.PluginError(
                                'Your from_telegram plugin config contains errors, please correct them.'
                            )
                    else:
                        logger.debug('Ignored entry, not match on field {}: {}', field, entry)
                        accept = False
                        break

            # Append the entry
            if accept:
                entries.append(entry)
                logger.debug('Added entry {}', entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(TelegramInput, 'from_telegram', api_ver=2)
