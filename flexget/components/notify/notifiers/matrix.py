import asyncio

from loguru import logger
from nio import AsyncClient

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginError

plugin_name = 'matrix'

logger = logger.bind(name=plugin_name)


class MatrixNotifier:
    """Send messages via Matrix.

    The ``matrix`` extra is required to be installed.
    Install it with: ``pip install flexget[matrix]``

    Required fields:

      - ``server``
      - one of::

        - ``token``
        - ``user`` and ``password``

      - one of::

        - ``room_id``
        - ``room_address``

    ``server``
        Matrix server hostname to integrate to, e.g. ``https://matrix.org``.

    ``token``
        View in Element Desktop -> settings ->  Help & About -> Advanced -> Access Token.

    ``user``
        ``@user_id:user_server``, e.g., ``@gazpachoking:matrix.org``

    ``password``
        Your password

    ``room_id``
        View in Element Desktop -> room settings -> Advanced -> Access Token. It should start with ``#``.

    ``room_address``
        View in Element Desktop -> room settings -> General -> Internal room ID. It should start with ``!``.

    Example 1::

      notify:
        entries:
          via:
            - matrix:
                server: https://matrix.org
                token: mat_K0a8IbdhQL5EsSghilk0axaTeOiUKq_dsBde4
                room_id: !yVNsbqQZjUqpxOyEgk:matrix.org

    Example 2::

      notify:
        entries:
          via:
            - matrix:
                server: https://matrix.org
                user: @gazpachoking:matrix.org
                password: ZrJ32Der0ret
                room_address: #flexget:matrix.org
    """

    schema = {
        'type': 'object',
        'properties': {
            'server': {'type': 'string'},
            'token': {'type': 'string'},
            'user': {'type': 'string'},
            'password': {'type': 'string'},
            'room_id': {'type': 'string'},
            'room_address': {'type': 'string'},
        },
        'required': ['server'],
        'additionalProperties': False,
        'allOf': [
            {'oneOf': [{'required': ['token']}, {'required': ['user', 'password']}]},
            {'oneOf': [{'required': ['room_id']}, {'required': ['room_address']}]},
        ],
    }

    def notify(self, title, message, config):
        """Send notification to Matrix room."""
        asyncio.run(self.main(message, config))

    async def main(self, message, config):
        client = AsyncClient(config['server'])
        try:
            if config['token']:
                client.access_token = config['token']
            else:
                client.user = config['user']
                logger.info(await client.login(config['password']))
            if config['room_id']:
                room_id = config['room_id']
            else:
                room_id = (await client.join(config['room_address'])).room_id
            response = await client.room_send(
                room_id=room_id,
                message_type='m.room.message',
                content={'msgtype': 'm.text', 'body': message},
            )
            if response.status_code == 200:
                logger.success('Successfully sent message')
            else:
                logger.error('Failed to send message')
                raise PluginError('Failed to send message', logger)
        finally:
            await client.close()


@event('plugin.register')
def register_plugin():
    plugin.register(MatrixNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])
