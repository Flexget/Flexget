from loguru import logger
from requests.exceptions import RequestException

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginWarning
from flexget.utils.requests import Session as RequestSession

requests = RequestSession(max_retries=3)

plugin_name = 'matrix'

logger = logger.bind(name=plugin_name)


def urljoin(*args):
    """
    Author: Rune Kaagaard
    Joins given arguments into an url. Trailing but not leading slashes are
    stripped for each argument.
    """
    return "/".join(str(x).rstrip('/') for x in args)


class MatrixNotifier:
    """
    Sends messages via Matrix. The MatrixHttpApi library is required to be installed.
    Install it with: `pip install matrix_client`

    All fields are required.

    server: Matrix hostname to integrate to (required)
    token: Is available in Element under Help/About. (required)
    room_id: Is available in Element under room settings. (required)

    Example::

      notify:
        entries:
          via:
            - matrix:
                server: "https://matrix.org"
                token: sender's token
                room_id: room identifier
    """

    schema = {
        'type': 'object',
        'properties': {
            'server': {'type': 'string'},
            'token': {'type': 'string'},
            'room_id': {'type': 'string'},
        },
        'required': ['server', 'token', 'room_id'],
        'additionalProperties': False,
    }

    __version__ = '0.3'

    def notify(self, title, message, config):
        """
        Send notification to Matrix Room
        """
        notification = {'body': message, 'msgtype': "m.text"}
        room = urljoin(
            config['server'],
            "_matrix/client/r0/rooms",
            config['room_id'],
            "send/m.room.message?access_token=" + config['token'],
        )
        try:
            requests.post(room, json=notification)
        except RequestException as e:
            raise PluginWarning(e.args[0]) from e


@event('plugin.register')
def register_plugin():
    plugin.register(MatrixNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])
