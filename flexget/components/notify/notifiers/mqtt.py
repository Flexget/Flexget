import json

from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.plugin import DependencyError, PluginWarning

from hashlib import sha256
import ssl

plugin_name = 'mqtt'
logger = logger.bind(name=plugin_name)

try:
    import paho.mqtt.client as mqtt 
except ImportError as e:
    logger.verbose('Error importing paho.mqtt.client: {}', e)
    raise DependencyError(
        plugin_name, 'paho.mqtt.client', 'paho-mqtt python module required. ImportError: %s' % e
    )

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
                [certificates: 
                    server_ca_cert: /path/to/pem/encoded/server_ca_certificate.crt
                    client_cert: /path/to/pem/encoded/client_certificate.crt
                    client_key: /path/to/pem/encoded/client_certificate.key
                    validate_broker_cert: True/False
                    tls_version: ['tlsv1.2', 'tlsv1.1', 'tlsv1', '']
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
            'broker_transport': {'type': 'string', 'default': 'tcp', 'enum': ['tcp', 'websockets']},
            'broker_protocol': {'type': 'string', 'default': 'MQTTv311', 'enum': ['MQTTv31', 'MQTTv311']}, 
            'username': {'type': 'string', 'default': ''},
            'password': {'type': 'string', 'default': ''},
            'certificates': {
                'type': 'object',
                'properties': {
                    'server_ca_cert': {'type': 'string', 'default': ''},
                    'client_cert': {'type': 'string', 'default': ''},
                    'client_key': {'type': 'string', 'default': ''},
                    'validate_broker_cert': {'type': 'boolean', 'default': True},
                    'tls_version': {'type': 'string', 'default': 'tlsv1.2', 'enum': ['tlsv1.2', 'tlsv1.1', 'tlsv1', '']},
                },
                'additionalProperties': False,
            },
            'qos': {'type': 'integer', 'minimum': 0, 'maximum': 2, 'default': 0},
            "retain": {"type": "boolean", 'default': False},
        },
        'additionalProperties': False,
        'required': ['broker_address','topic'],
    }

    def notify(self, title, message, config):
        """
        Publish to an MQTT topic
        """

        config['title'] = title
        config['message'] = message
        config['payload'] = '{} - {}'.format(config.get('title'),config.get('message'))

        class PublishMQTT(mqtt.Client):

            def __init__(self, config):

                self.config = config
                self.logger = logger
                mqtt.Client.__init__(self)

                logger.trace('MQTT notify config={}'.format(str(self.config)))

                if self.config.get('username',False):
                    logger.debug('Credential passwords s are redacted to protect the innocent...')
                    logger.debug('Auth credentials: username=[{}] password sha256 hash is "{}"'.format(self.config.get('username'),sha256(str(self.config.get('password','')).encode('utf-8')).hexdigest()))
                    logger.debug('You can validate them yourself by calculating the sha256 hex digest of your password string (google is your friend if you do not know how to do this)')
                    logger.debug('Note: a password that is not provided will hash to "{}"'.format(sha256(str('').encode('utf-8')).hexdigest()))                    

                if self.config.get('certificates',''):
                    certs = self.config.get('certificates',{})
                    logger.debug('TLS certificate config: {}'.format(str(certs)))

                    tls_version_map = {'tlsv1.2': ssl.PROTOCOL_TLSv1_2, 'tlsv1.1': ssl.PROTOCOL_TLSv1_1, 'tlsv1': ssl.PROTOCOL_TLSv1, '': None}
                    tls_version = tls_version_map.get(certs.get('tls_version'),ssl.PROTOCOL_TLSv1_2)
                    logger.verbose('TLS version is {}'.format(str(tls_version)))

                    if certs.get('validate_broker_cert',True):
                        cert_required = ssl.CERT_REQUIRED
                    else:
                        cert_required = ssl.CERT_NONE
                    logger.verbose('TLS cert_required={}'.format(str(cert_required)))

                    self.tls_set(ca_certs=certs.get('server_ca_cert',None),
                                  certfile=certs.get('client_cert',None),
                                  keyfile=certs.get('client_key',None),
                                  cert_reqs=cert_required,
                                  tls_version=tls_version)

                    if not certs.get('validate_broker_cert',None):
                        self.tls_insecure_set(True)                       
                        logger.debug('TLS insecure cert mode enabled. Server cert will not be validated')
                    else:
                        logger.debug('TLS secure cert mode enabled. Server cert will be validated')

                if self.config.get('username',False) or self.config.get('password',False):
                    self.username_pw_set=(self.config.get('username',None),self.config.get('password',None))

                self.on_connect = self.on_connect_cb
                self.on_disconnect = self.on_disconnect_cb
                self.on_publish = self.on_publish_cb

                logger.verbose("Connecting to {}:{}".format(self.config.get('broker_address'),str(self.config.get('broker_port'))))
                self.connect(self.config.get('broker_address'), self.config.get('broker_port'), self.config.get('broker_timeout'))

                logger.verbose('Publishing message [{}] to topic [{}] '.format(self.config.get('payload'),self.config.get('topic')))
                ret = self.publish(self.config.get('topic'), self.config.get('payload'), qos=self.config.get('qos'), retain=self.config.get('retain'))

                logger.verbose("MQTT publishe result is {}".format(str(ret)))

                self.disconnect()

            def on_connect_cb(self, userdata, rc):
                self.logger.verbose('MQTT connected with result code {}'.format(str(rc)))

            def on_disconnect_cb(self, userdata, rc):
                self.logger.verbose('MQTT disconnected with result code {}'.format(str(rc)))

            def on_publish_cb(self, userdata, mid):
                self.logger.verbose('MQTT message was successfully published to broker as messageID={}'.format(str(mid)))

        PublishMQTT(config)

@event('plugin.register')
def register_plugin():
    plugin.register(MQTTNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])
