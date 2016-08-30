from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import io
import logging

from flask.helpers import send_file
from flask_restplus import inputs

from flexget.api import api, APIResource, ApiError
from flexget.utils.tools import cached_resource

log = logging.getLogger('cached')

cached_api = api.namespace('cached', description='Cache remote resources')

cached_parser = api.parser()
cached_parser.add_argument('url', required=True, help='URL to cache')
cached_parser.add_argument('force', type=inputs.boolean, default=False, help='Force fetching remote resource')


@cached_api.route('/')
class CachedResource(APIResource):
    @api.response(200, description='Return file')
    @api.response(ApiError)
    @api.doc(parser=cached_parser)
    def get(self, session=None):
        args = cached_parser.parse_args()
        url = args.get('url')
        force = args.get('force')
        try:
            file_path, mime_type = cached_resource(url, force)
        except OSError as e:
            return ApiError(e)
        return send_file(file_path, mimetype=mime_type)
