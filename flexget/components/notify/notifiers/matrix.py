import logging

from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.plugin import DependencyError, PluginWarning


plugin_name = 'matrix'

logger = logger.bind(name=plugin_name)


class MatrixNotifier:
    """
    Sends messages via Matrix. The MatrixHttpApi library is required to be installed.
    Install it with: `pip install matrix_client`

    All fields are required.

    token: Is available in Element under Help/About.
    roomId: Is available in Element under room settings.

    Example::

      notify:
        entries:
          via:
            - matrix:
                server: "https://matrix.org"
                token: sender's token
                roomid: room identifier
    """

    schema = {
        'type': 'object',
        'properties': {
            'server': {'type': 'string'},
            'token': {'type': 'string'},
            'roomid': {'type': 'string'},
        },
        'required': ['server', 'token', 'roomid'],
        'additionalProperties': False,
    }

    __version__ = '0.1'

    def notify(self, title, message, config):
        try:
            from matrix_client.api import MatrixHttpApi  # noqa
        except ImportError as e:
            logger.debug('Error importing MatrixHttpApi: {}', e)
            raise DependencyError(
                plugin_name, 'matrix_client', 'matrix_client module required. ImportError: %s' % e
            )
        #TODO: Is dns required to be loaded for the matrix_client module?
        try:
            import dns  # noqa
        except ImportError:
            try:
                import dnspython  # noqa
            except ImportError as e:
                logger.debug('Error importing dnspython: {}', e)
                raise DependencyError(
                    plugin_name, 'dnspython', 'dnspython module required. ImportError: %s' % e
                )

        message = '%s\n%s' % (title, message)
        logger.debug('Sending Matrix notification about: {}', message)
        logging.getLogger('matrix').setLevel(logging.CRITICAL)
        matrix = MatrixHttpApi(token=config['server'], token=config['token'])
        response = matrix.send_message(config['roomid'], message)



@event('plugin.register')
def register_plugin():
    plugin.register(MatrixNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])
