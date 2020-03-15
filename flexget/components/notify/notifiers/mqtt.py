import json

from loguru import logger

from hashlib import sha256
import ssl

from flexget import plugin
#from flexget.config_schema import one_or_more
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
                [enable_encrypted_communication: True/False]
                [certificates:
                    broker_ca_cert: /path/to/pem/encoded/broker_ca_certificate.crt
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
            'enable_encrypted_communication': {'type': 'boolean', 'default': False},
            'certificates': {
                'type': 'object',
                'properties': {
                    'broker_ca_cert': {'type': 'string', 'default': ''},
                    'client_cert': {'type': 'string', 'default': ''},
                    'client_key': {'type': 'string', 'default': ''},
                    'validate_broker_cert': {'type': 'boolean', 'default': True},
                    'tls_version': {'type': 'string', 'default': '', 'enum': ['tlsv1.2', 'tlsv1.1', 'tlsv1', '']},
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
        try:
            import paho.mqtt.client as mqtt

        except ImportError as e:
            logger.verbose('Error importing paho.mqtt.client: {}', e)
            raise DependencyError(
                plugin_name, 'paho.mqtt.client', 'paho-mqtt python module is required for MQTT notify plugin. ImportError: %s' % e
            )

        config['title'] = title
        config['message'] = message
        config['payload'] = '{} - {}'.format(config.get('title'),config.get('message'))

        class PublishMQTT(mqtt.Client):
            conn_rc_description_map = { 0: 	'Connection Accepted',
                                1: 	'Connection Refused, unacceptable protocol version - The Server does not support the level of the MQTT protocol requested by the Client',
                                2: 	'Connection Refused, identifier rejected - The Client identifier is correct UTF-8 but not allowed by the Server',
                                3: 	'Connection Refused, Server unavailable - The Network Connection has been made but the MQTT service is unavailable',
                                4: 	'Connection Refused, bad user name or password - The data in the user name or password is malformed',
                                5: 	'Connection Refused, not authorized - The Client is not authorized to connect' }

            MQTT_proto_map = { 'MQTTv31' : mqtt.MQTTv311,
                               'MQTTv311': 	mqtt.MQTTv31 }

            def __init__(self, config):

                try:
                    self.config = config
                    self.logger = logger

                    logger.trace('MQTT notify config={}',str(self.config))

                    mqtt.Client.__init__(self, protocol=PublishMQTT.MQTT_proto_map.get(self.config.get('broker_protocol',mqtt.MQTTv311)), transport=self.config.get('broker_transport', 'tcp') )

                    self.enable_logger(logger=logger)

                    self.on_log = PublishMQTT.on_log_cb
                    self.on_publish = PublishMQTT.on_publish_cb
                    self.on_disconnect = PublishMQTT.on_disconnect_cb

                    #Handle SSL/TLS communication w/out certificate authentication
                    if not self.config.get('certificates',{}).get('client_cert',False) and self.config.get('enable_encrypted_communication',False):
                        self.tls_set(ca_certs=certs.get('broker_ca_cert'),
                                      certfile=None,
                                      keyfile=None,
                                      cert_reqs=ssl.CERT_NONE)

                        self.tls_insecure_set(True)

                        logger.verbose('Basic SSL/TLS encrypted communications enabled')
                        logger.verbose('TLS insecure cert mode enabled. Broker cert will not be validated')

                    #Handle SSL/TLS communication with certificate authentication
                    if self.config.get('certificates',False):
                        certs = self.config.get('certificates',{})
                        logger.debug('TLS certificate config: {}',str(certs))

                        tls_version_map = {'tlsv1.2': ssl.PROTOCOL_TLSv1_2, 'tlsv1.1': ssl.PROTOCOL_TLSv1_1, 'tlsv1': ssl.PROTOCOL_TLSv1, '': None}
                        tls_version = tls_version_map.get(certs.get('tls_version'),ssl.PROTOCOL_TLSv1_2)
                        logger.verbose('TLS version is {}',str(tls_version))

                        cert_required = ssl.CERT_REQUIRED if certs.get('validate_broker_cert', True) else ssl.CERT_NONE

                        self.tls_set(ca_certs=certs.get('broker_ca_cert'),
                                      certfile=certs.get('client_cert'),
                                      keyfile=certs.get('client_key'),
                                      cert_reqs=cert_required,
                                      tls_version=tls_version)

                        if not certs.get('validate_broker_cert'):
                            self.tls_insecure_set(True)

                            logger.debug('TLS insecure cert mode enabled. Broker cert will not be validated')
                        else:
                            logger.debug('TLS secure cert mode enabled. Broker cert will be validated')

                    #Handle user/pass authentication
                    if self.config.get('username',False) or self.config.get('password',False):
                        logger.debug('Credential passwords s are redacted to protect the innocent...')
                        logger.debug('Auth credentials: username=[{}] password sha256 hash is "{}"',self.config.get('username'),sha256(str(self.config.get('password')).encode('utf-8')).hexdigest())
                        logger.debug('You can validate them yourself by calculating the sha256 hex digest of your password string (google is your friend if you do not know how to do this)')
                        logger.debug('Note: a password that is not provided (i.e. None) will hash to "{}"',sha256(str(None).encode('utf-8')).hexdigest())

                        self.username_pw_set=(self.config.get('username'),self.config.get('password'))

                    logger.verbose("Connecting to {}:{}",self.config.get('broker_address'),str(self.config.get('broker_port')))
                    self.connect(self.config.get('broker_address'), self.config.get('broker_port'), self.config.get('broker_timeout'))
                    logger.verbose("Connected to MQTT broker")

                    logger.verbose('Publishing message [{}] to topic [{}] ',self.config.get('payload'),self.config.get('topic'))
                    publish_info = self.publish(self.config.get('topic'), self.config.get('payload'), qos=self.config.get('qos'), retain=self.config.get('retain'))
                    logger.verbose("Notification sent to broker, waiting for callback response to confirm publishing success - rc={}",publish_info)

                    self.loop(timeout=self.config.get('broker_timeout'))
                    self.loop_start()  #Non-blocking

                    #self.loop_forever()  # blocking

                except Exception as e:
                    raise PluginWarning('Error publishing to MQTT broker:  %s' % e)

            def on_log_cb(self, userdata, level, buff):
                self.logger.verbose(str(buff))

            def on_publish_cb(self, userdata, mid):
                self.logger.verbose('MQTT on_publish callback -  message was successfully published to broker as messageID={}',str(mid))
                self.disconnect()

            def on_disconnect_cb(self, userdata, rc):
                self.logger.verbose('MQTT on_disconnect callback - disconnected with result code {} [{}]',str(rc),PublishMQTT.conn_rc_description_map.get(rc),'Unknown')
                self.loop_stop()

        PublishMQTT(config)
        

@event('plugin.register')
def register_plugin():
    plugin.register(MQTTNotifier, plugin_name, api_ver=2, interfaces=['notifiers'])
