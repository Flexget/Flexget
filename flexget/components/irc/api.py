from flask import jsonify
from flask_restx import inputs

from flexget.api import APIResource, api
from flexget.api.app import (
    BadRequest,
    NotFoundError,
    base_message_schema,
    empty_response,
    success_response,
)

irc_api = api.namespace('irc', description='View and manage IRC connections')

irc_parser = api.parser()
irc_parser.add_argument(
    'name', help='Name of connection. Leave empty to apply to all connections.'
)


class ObjectsContainer:
    connection_object = {
        'type': 'object',
        'properties': {
            'alive': {'type': 'boolean'},
            'channels': {
                'type': 'array',
                'items': {'type': 'object', 'patternProperties': {r'\w': {'type': 'integer'}}},
            },
            'connected_channels': {'type': 'array', 'items': {'type': 'string'}},
            'port': {'type': 'integer'},
            'server': {'type': 'string'},
        },
    }

    connection = {'type': 'object', 'patternProperties': {r'\w': connection_object}}

    return_response = {'type': 'array', 'items': connection}


return_schema = api.schema_model('irc.connections', ObjectsContainer.return_response)


@irc_api.route('/connections/')
@api.doc(expect=[irc_parser])
class IRCStatus(APIResource):
    @api.response(200, model=return_schema)
    @api.response(NotFoundError)
    @api.response(BadRequest)
    def get(self, session=None):
        """Returns status of IRC connections"""
        from .irc import irc_manager

        if irc_manager is None:
            raise BadRequest('IRC daemon does not appear to be running')

        args = irc_parser.parse_args()
        name = args.get('name')
        try:
            status = irc_manager.status(name)
        except ValueError as e:
            raise NotFoundError(e.args[0])
        return jsonify(status)


@irc_api.route('/connections/enums/')
class IRCEnums(APIResource):
    @api.response(200, model=empty_response)
    def get(self, session=None):
        """Get channel status enumeration meaning"""
        try:
            from irc_bot import simple_irc_bot
        except ImportError:
            raise BadRequest('irc_bot dep is not installed')
        return jsonify(simple_irc_bot.IRCChannelStatus().enum_dict)


@irc_api.route('/restart/')
@api.doc(expect=[irc_parser])
class IRCRestart(APIResource):
    @api.response(200, model=base_message_schema)
    @api.response(NotFoundError)
    @api.response(BadRequest)
    def get(self, session=None):
        """Restarts IRC connections"""
        from .irc import irc_manager

        if irc_manager is None:
            raise BadRequest('IRC daemon does not appear to be running')

        args = irc_parser.parse_args()
        connection = args.get('name')
        try:
            irc_manager.restart_connections(connection)
        except KeyError:
            raise NotFoundError(f'Connection {connection} is not a valid IRC connection')
        return success_response('Successfully restarted connection(s)')


irc_stop_parser = irc_parser.copy()
irc_stop_parser.add_argument(
    'wait', type=inputs.boolean, default=False, help='Wait for connection to exit gracefully'
)


@irc_api.route('/stop/')
@api.doc(expect=[irc_stop_parser])
class IRCStop(APIResource):
    @api.response(200, model=base_message_schema)
    @api.response(NotFoundError)
    @api.response(BadRequest)
    def get(self, session=None):
        """Stops IRC connections"""
        from .irc import irc_manager

        if irc_manager is None:
            raise BadRequest('IRC daemon does not appear to be running')

        args = irc_stop_parser.parse_args()
        name = args.get('name')
        wait = args.get('wait')
        try:
            irc_manager.stop_connections(wait=wait, name=name)
        except KeyError:
            raise NotFoundError(f'Connection {name} is not a valid IRC connection')
        return success_response('Successfully stopped connection(s)')
