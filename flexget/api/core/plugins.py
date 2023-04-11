from math import ceil
from typing import TYPE_CHECKING, List, Optional

from flask import Response, jsonify, request
from flask_restx import inputs
from loguru import logger
from sqlalchemy.orm import Session

from flexget.api import APIResource, api
from flexget.api.app import BadRequest, NotFoundError, etag, pagination_headers
from flexget.config_schema import JsonSchema
from flexget.plugin import DependencyError, get_plugin_by_name, get_plugins

logger = logger.bind(name='plugins')

plugins_api = api.namespace('plugins', description='Get Flexget plugins')


class ObjectsContainer:
    phase_object = {
        'type': 'object',
        'properties': {'phase': {'type': 'string'}, 'priority': {'type': 'integer'}},
    }

    plugin_object = {
        'type': 'object',
        'properties': {
            'name': {'type': 'string'},
            'api_ver': {'type': 'integer'},
            'builtin': {'type': 'boolean'},
            'category': {'type': ['string', 'null']},
            'contexts': {'type': 'array', 'items': {'type': 'string'}},
            'debug': {'type': 'boolean'},
            'interfaces': {'type': 'array', 'items': {'type': 'string'}},
            'phase_handlers': {'type': 'array', 'items': phase_object},
        },
    }

    plugin_list_reply = {'type': 'array', 'items': plugin_object}


plugin_schema = api.schema_model('plugin_object', ObjectsContainer.plugin_object)
plugin_list_reply_schema = api.schema_model(
    'plugin_list_reply', ObjectsContainer.plugin_list_reply
)

plugin_parser = api.parser()
plugin_parser.add_argument(
    'include_schema',
    type=inputs.boolean,
    default=False,
    help='Include plugin schema. This will increase response size',
)

plugins_parser = api.pagination_parser(plugin_parser)

plugins_parser.add_argument(
    'interface', case_sensitive=False, help='Show plugins which implement this interface'
)
plugins_parser.add_argument(
    'phase', case_sensitive=False, help='Show plugins that act on this phase'
)

if TYPE_CHECKING:
    from typing import TypedDict

    class _PhaseHandler(TypedDict):
        phase: str
        priority: int

    class PluginDict(TypedDict, total=False):
        name: str
        api_ver: int
        builtin: bool
        category: Optional[str]
        debug: bool
        interfaces: Optional[List[str]]
        phase_handlers: List[_PhaseHandler]
        schema: Optional[JsonSchema]


def plugin_to_dict(plugin) -> 'PluginDict':
    return {
        'name': plugin.name,
        'api_ver': plugin.api_ver,
        'builtin': plugin.builtin,
        'category': plugin.category,
        'debug': plugin.debug,
        'interfaces': plugin.interfaces,
        'phase_handlers': [
            {'phase': handler, 'priority': event.priority}
            for handler, event in plugin.phase_handlers.items()
        ],
    }


@plugins_api.route('/')
class PluginsAPI(APIResource):
    @etag(cache_age=3600)
    @api.response(200, model=plugin_list_reply_schema)
    @api.response(BadRequest)
    @api.response(NotFoundError)
    @api.doc(parser=plugins_parser)
    def get(self, session: Session = None) -> Response:
        """Get list of registered plugins"""
        args = plugins_parser.parse_args()

        # Pagination and sorting params
        page = args['page']
        per_page = args['per_page']

        # Handle max size limit
        if per_page > 100:
            per_page = 100

        start = per_page * (page - 1)
        stop = start + per_page

        plugin_list = []
        try:
            for plugin in get_plugins(phase=args['phase'], interface=args['interface']):
                p = plugin_to_dict(plugin)
                if args['include_schema']:
                    p['schema'] = plugin.schema
                plugin_list.append(p)
        except ValueError as e:
            raise BadRequest(str(e))

        total_items = len(plugin_list)

        sliced_list = plugin_list[start:stop]

        # Total number of pages
        total_pages = int(ceil(total_items / float(per_page)))

        if page > total_pages and total_pages != 0:
            raise NotFoundError(f'page {page} does not exist')

        # Actual results in page
        actual_size = min(per_page, len(sliced_list))

        # Get pagination headers
        pagination = pagination_headers(total_pages, total_items, actual_size, request)

        rsp = jsonify(sliced_list)

        # Add link header to response
        rsp.headers.extend(pagination)
        return rsp


@plugins_api.route('/<string:plugin_name>/')
class PluginAPI(APIResource):
    @etag(cache_age=3600)
    @api.response(BadRequest)
    @api.response(200, model=plugin_schema)
    @api.doc(parser=plugin_parser, params={'plugin_name': 'Name of the plugin to return'})
    def get(self, plugin_name: str, session=None):
        """Return plugin data by name"""
        args = plugin_parser.parse_args()
        try:
            plugin = get_plugin_by_name(plugin_name, issued_by='plugins API')
        except DependencyError as e:
            raise BadRequest(e.message)
        p = plugin_to_dict(plugin)
        if args['include_schema']:
            p['schema'] = plugin.schema
        return jsonify(p)
