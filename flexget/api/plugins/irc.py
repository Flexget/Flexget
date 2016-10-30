from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

from flask import jsonify
from flask.ext.restplus import inputs
from flexget.api import api, APIResource
from flexget.api.app import BadRequest, NotFoundError, success_response, base_message_schema

irc_api = api.namespace('irc', description='View and manage IRC connections')

irc_parser = api.parser()
irc_parser.add_argument('name', help='Name of connection. Leave empty to apply to all connections.')


@irc_api.route('/connections/')
@api.doc(parser=irc_parser)
class IRCStatus(APIResource):
    @api.response(200)
    @api.response(NotFoundError)
    @api.response(BadRequest)
    def get(self, session=None):
        """Returns status of IRC connections"""
        from flexget.plugins.daemon.irc import irc_manager
        if irc_manager is None:
            raise BadRequest('IRC daemon does not appear to be running')

        args = irc_parser.parse_args()
        connection = args.get('name')
        if connection:
            try:
                status = irc_manager.status(connection)
            except ValueError as e:
                raise NotFoundError(e.args[0])
        else:
            status = irc_manager.status_all()
        return jsonify(status)


@irc_api.route('/restart/')
@api.doc(parser=irc_parser)
class IRCRestart(APIResource):
    @api.response(200, model=base_message_schema)
    @api.response(NotFoundError)
    @api.response(BadRequest)
    def get(self, session=None):
        """Restarts IRC connections"""
        from flexget.plugins.daemon.irc import irc_manager
        if irc_manager is None:
            raise BadRequest('IRC daemon does not appear to be running')

        args = irc_parser.parse_args()
        connection = args.get('name')
        try:
            if connection:
                irc_manager.restart_connection(connection)
            else:
                irc_manager.restart_connections()
        except KeyError:
            raise NotFoundError('Connection {} is not a valid IRC connection'.format(connection))
        return success_response('Successfully restarted connection(s)')


irc_stop_parser = irc_parser.copy()
irc_stop_parser.add_argument('wait', type=inputs.boolean, default=False, help='Wait for connection to exit gracefully')


@irc_api.route('/stop/')
@api.doc(parser=irc_parser)
class IRCStop(APIResource):
    @api.response(200, model=base_message_schema)
    @api.response(NotFoundError)
    @api.response(BadRequest)
    def get(self, session=None):
        """Stops IRC connections"""
        from flexget.plugins.daemon.irc import irc_manager
        if irc_manager is None:
            raise BadRequest('IRC daemon does not appear to be running')

        args = irc_parser.parse_args()
        connection = args.get('name')
        wait = args.get('wait')
        try:
            if connection:
                irc_manager.stop_connection(connection)
            else:
                irc_manager.stop_connections(wait)
        except KeyError:
            raise NotFoundError('Connection {} is not a valid IRC connection'.format(connection))
        return success_response('Successfully stopped connection(s)')
