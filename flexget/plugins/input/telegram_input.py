"""Plugin for telegram input"""
import re
from loguru import logger
from flexget.config_schema import one_or_more
from flexget import plugin
from flexget.entry import Entry
from flexget.event import event

logger = logger.bind(name='telegram_input')

_TELEGRAM_API_URL = "https://api.telegram.org/"


class TelegramInput:
    """
    Parse any messages from Telegram and fills fields with regex

    Example::

      token: <token>
      clean_update: yes
      whitelist:
        - username: <my_username>
        - group: <my_group>
        - fullname:
            first: <my_first_name>
            sur: <my_surname>
      entry:
        <field>: <regexp to match value>

    Note: If not declated, title will be the message
    """

    schema = {
        'type': 'object',
        'properties': {
            'token': {'type': 'string'},
            'types' : one_or_more({'type': 'string', 'enum': ['private', 'group']}),
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

            'clean_update': {'type': 'boolean','default': True},
            'entry': {
                'type': 'object',
                'properties': {
                    'url': {'type': 'string', 'format': 'regex'},
                    'title': {'type': 'string', 'format': 'regex'},
                },
                'additionalProperties': {'type': 'string', 'format': 'regex'},
                'required': [],
            },
        },
        'required': ['token'],
        'additonalProperties': False,
    }

    @plugin.internet(logger)
    def on_task_input(self, task, config):
        #Load The Configs
        token = config['token']
        clean_update = config['clean_update']
        entry_config = config.get('entry')
        whitelist = config.get('whitelist')
        types = config.get('types')

        #Defaults
        if types is None:
            types = ['private', 'group']

        #Get Last Checked ID
        update_id = task.simple_persistence.get(token+'_update_id')

        #Set Last Checked ID as Offset
        offset = ""
        if update_id is not None:
            update_id += 1
            offset = "?offset="+str(update_id)
        
        #The Target URL
        url = _TELEGRAM_API_URL + "bot" + token + "/getUpdates" + offset  

        #Get Telegram Updates
        try:
            response = task.requests.get(
                url, timeout=60, raise_status=False
            ).json()
        except:
            logger.error("Error getting telegram update")
            return

        #We have a error
        if response['ok'] == False:
            logger.error("Telegram updater returned error {}: {}", response['error_code'], response['description'] )
            return

        #Get All New Messages
        messages = response['result']

        entries = []
        for message in messages:
            #This is the ID
            update_id = message['update_id']

            #If desired update the last ID for the Bot
            if clean_update == True:
                task.simple_persistence[token+'_update_id'] = update_id
            
            #We Don't care if it's not a message or no text
            if 'message' not in message:
                continue

            if 'text' not in message['message']:
                continue

            if 'chat' not in message['message']:
                continue

            if 'type' not in message['message']['chat']:
                continue

            logger.debug("Income message: {}", message)

            #Create Base Entry
            text = message['message']['text']
            entry = Entry()
            entry['title'] =  text

            #We need a url, so we add a dummy
            entry['url']   = "http://localhost?update_id="+str(update_id)

            #Store the message if we need to use it in other plugins
            entry['telegram_message'] =  message['message']
            
            #Check Types
            if types is not None:
                if message['message']['chat']['type'] not in types:
                    logger.debug("Ignoring message because of invalid type {}",message)
                    continue

            #Check From
            append = True
            if whitelist is not None:
                append = False
                for i in whitelist:
                    if 'username' in i and i['username'] == message['message']['from']['username']:
                        logger.debug("WhiteListing: Username {}",message['message']['from']['username'])
                        append = True
                        break
                    elif ('fullname' in i) and (i ['fullname']['first'] == message['message']['from']['first_name'] and i['fullname']['sur'] == message['message']['from']['last_name']):
                        logger.debug("WhiteListing: Full Name {} {}",message['message']['from']['first_name'],message['message']['from']['last_name'])
                        append = True
                        break
                    elif 'group' in i:
                        if message['message']['chat']['type'] == 'group':
                            if message['message']['chat']['title'] == i['group']:
                                logger.debug("WhiteListing: Group {}",message['message']['chat']['title'])
                                append = True
                                break

                if append != True:
                    logger.debug("Ignoring message because of no white list match {}",message)
                    continue
            
            #Process the entry config
            if entry_config is None:
                pass
            else:
                for field, regexp in entry_config.items():
                    match = re.search(regexp, text)
                    if match:
                        try:
                            # add field to entry
                            entry[field] = match.group(1)
                        except IndexError:
                            logger.error('Regex for field `{}` must contain a capture group', field)
                            raise plugin.PluginError(
                                'Your telegram_input plugin config contains errors, please correct them.'
                            )
                    else:
                        logger.debug('Ignored entry, not match on field {}: {}',field, entry)
                        append = False
                        break
            
            #Append the entry
            if append == True:
                entries.append(entry)
                logger.debug('Added entry {}', entry)

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(TelegramInput, 'telegram_input', api_ver=2)