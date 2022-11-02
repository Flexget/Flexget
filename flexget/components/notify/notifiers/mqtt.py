import ssl
from hashlib import sha256

from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.plugin import DependencyError, PluginWarning

plugin_name = 'mqtt'
logger = logger.bind(name=plugin_name)


class MQTTNotifier:
    """
    Example::
      notify:
        entries:
          via:
            - mqtt:
                broker_address: "iot.eclipse.org"
                topic: "flexget/notifications"
                [broker_port: 1883]
                [broker_timeout: 30]
                [broker_transport: ['tcp','websockets'] ]
                [broker_protocol: ['MQTTv31', 'MQTTv311'] ]
                [username: yourUsernameHere]
                [password: yourPasswordHere]
                [encrypted_communication: True/False]
                [certificates:
                    broker_ca_cert: /path/to/pem/encoded/broker_ca_certificate.crt
                    client_cert: /path/to/pem/encoded/client_certificate.crt
                    client_key: /path/to/pem/encoded/client_certificate.key
                    validate_broker_cert: True/False
                    tls_version: ['tlsv1.2', 'tlsv1.1', 'tlsv1']
                ]
                [qos: [0,1,2] ]
                [retain: True/False]
    """

    schema = {
        'type': 'object',
        'properties': {
            'topic': {'type': 'string'},
            'broker_address': {'type': 'string'},
            'broker_port': {'type': 'integer', 'default': 1883},
            'broker_timeout': {'type': 'integer', 'default': 30},
            'broker_transport': {
                'type': 'string',
                'default': 'tcp',
                'enum': ['tcp', 'websockets'],
            },
            'broker_protocol': {
                'type': 'string',
                'default': 'MQTTv311',
                'enum': ['MQTTv31', 'MQTTv311'],
            },
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'encrypted_communication': {'type': 'boolean', 'default': False},
            'certificates': {
                'type': 'object',
                'properties': {
                    'broker_ca_cert': {'type': 'string'},
                    'client_cert': {'type': 'string'},
                    'client_key': {'type': 'string'},
                    'validate_broker_cert': {'type': 'boolean', 'default': True},
                    'tls_version': {'type': 'string', 'enum': ['tlsv1.2', 'tlsv1.1', 'tlsv1', '']},
                },
                'additionalProperties': False,
            },
            'qos': {'type': 'integer', 'minimum': 0, 'maximum': 2, 'default': 0},
            "retain": {"type": "boolean", 'default': False},
        },
        'additionalProperties': False,
        'required': ['broker_address', 'topic'],
        'dependencies': {'password': ['username']},
    }

    def notify(self, title, message, config):
        """
        Publish to an MQTT topic
        """
        try:
            import paho.mqtt.client as mqtt

        except ImportError as e:
            logger.verbose('Error importing paho.mqtt.client: {}', e)
            raise DependencyError(
                plugin_name,
                'paho.mqtt.client',
                f'paho-mqtt python module is required for MQTT notify plugin. ImportError: {e}',
            )

        def on_log_cb(client, userdata, level, buff):
            logger.verbose(str(buff))

        def on_publish_cb(client, userdata, mid):
            logger.verbose(
                'MQTT on_publish callback -  message was successfully published to broker as messageID={}',
                mid,
            )
            client.disconnect()

        def on_disconnect_cb(client, userdata, rc):
            logger.verbose(
                'MQTT on_disconnect callback - disconnected with result code {} [{}]',
                rc,
                conn_rc_description_map.get(rc),
                'Unknown',
            )
            client.loop_stop()

        config['title'] = title
        config['message'] = message
        config['payload'] = f"{config['title']} - {config['message']}"

        conn_rc_description_map = {
            0: 'Connection Accepted',
            1: 'Connection Refused, unacceptable protocol version - The Server does not support the level of the MQTT protocol requested by the Client',
            2: 'Connection Refused, identifier rejected - The Client identifier is correct UTF-8 but not allowed by the Server',
            3: 'Connection Refused, Server unavailable - The Network Connection has been made but the MQTT service is unavailable',
            4: 'Connection Refused, bad user name or password - The data in the user name or password is malformed',
            5: 'Connection Refused, not authorized - The Client is not authorized to connect',
        }

        # Handle the MQTT broker protocol to be used
        if config.get('broker_protocol') == 'MQTTv311':
            config['broker_protocol_class'] = mqtt.MQTTv311
        else:
            config['broker_protocol_class'] = mqtt.MQTTv31

        logger.trace('MQTT notify config={}', config)

        # create the mqtt client
        client = mqtt.Client(
            protocol=config['broker_protocol_class'], transport=config['broker_transport']
        )

        client.enable_logger(logger=logger)

        client.on_log = on_log_cb
        client.on_publish = on_publish_cb
        client.on_disconnect = on_disconnect_cb

        # Handle SSL/TLS communication w/out certificate authentication
        if not config.get('certificates', {}).get('client_cert') and config.get(
            'encrypted_communication'
        ):
            client.tls_set(
                ca_certs=certs.get('broker_ca_cert'),
                certfile=None,
                keyfile=None,
                cert_reqs=ssl.CERT_NONE,
            )

            client.tls_insecure_set(True)

            logger.verbose('Basic SSL/TLS encrypted communications enabled')
            logger.verbose('TLS insecure cert mode enabled. Broker cert will not be validated')

        # Handle SSL/TLS communication with certificate authentication
        if config.get('certificates'):
            certs = config['certificates']
            logger.debug('TLS certificate config: {}', certs)

            tls_version_map = {
                'tlsv1.2': ssl.PROTOCOL_TLSv1_2,
                'tlsv1.1': ssl.PROTOCOL_TLSv1_1,
                'tlsv1': ssl.PROTOCOL_TLSv1,
                '': None,
            }
            tls_version = tls_version_map.get(certs.get('tls_version'), ssl.PROTOCOL_TLSv1_2)
            logger.verbose('TLS version is {}', tls_version)

            cert_required = (
                ssl.CERT_REQUIRED if certs.get('validate_broker_cert', True) else ssl.CERT_NONE
            )

            client.tls_set(
                ca_certs=certs.get('broker_ca_cert'),
                certfile=certs.get('client_cert'),
                keyfile=certs.get('client_key'),
                cert_reqs=cert_required,
                tls_version=tls_version,
            )

            if not certs.get('validate_broker_cert'):
                client.tls_insecure_set(True)
                logger.debug('TLS insecure cert mode enabled. Broker cert will not be validated')
            else:
                logger.debug('TLS secure cert mode enabled. Broker cert will be validated')

        # Handle user/pass authentication
        if config.get('username'):
            logger.debug('Credential passwords s are redacted to protect the innocent...')
            logger.debug(
                'Auth credentials: username=[{}] password sha256 hash is "{}"',
                config.get('username'),
                sha256(str(config.get('password')).encode('utf-8')).hexdigest(),
            )
            logger.debug(
                'You can validate them yourself by calculating the sha256 hex digest of your password string (google is your friend if you do not know how to do this)'
            )
            logger.debug(
                'Note: a password that is not provided (i.e. None) will hash to "{}"',
                sha256(str(None).encode('utf-8')).hexdigest(),
            )

            client.username_pw_set = (config.get('username'), config.get('password'))

        try:
            logger.verbose(
                "Connecting to {}:{}", config.get('broker_address'), config.get('broker_port')
            )
            client.connect(
                config.get('broker_address'),
                config.get('broker_port'),
                config.get('broker_timeout'),
            )
            logger.verbose("Connected to MQTT broker")
        except Exception as e:
            raise PluginWarning(f'Error connecting to MQTT broker: {e}')

        try:
            logger.verbose(
                'Publishing message [{}] to topic [{}] ',
                config.get('payload'),
                config.get('topic'),
            )
            publish_info = client.publish(
                config.get('topic'),
                config.get('payload'),
                qos=config.get('qos'),
                retain=config.get('retain'),
            )
            logger.verbose(
                "Notification sent to broker, waiting for callback response to confirm publishing success - rc={}",
                publish_info,
            )
        except Exception as e:
            raise PluginWarning(f'Error publishing to MQTT broker: {e}')

        client.loop(timeout=config.get('broker_timeout'))
        client.loop_start()


@event('plugin.register')
def register_plugin():
    plugin.register(MQTTNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])
