from __future__ import unicode_literals, division, absolute_import

from flask import jsonify

from flexget.api import api, APIResource
from flexget.plugins.api_tvdb import lookup_series

tvdb_api = api.namespace('tvdb', description='TheTVDB Shows')


@tvdb_api.route('/<string:search>/')
@api.doc(params={'search': 'TV Show name or TVDB ID'})
class TVDBSearchApi(APIResource):
    @api.response(200, 'Successfully found show')
    @api.response(404, 'No show found')
    def get(self, search, session=None):
        try:
            tvdb_id = int(search)
        except ValueError:
            tvdb_id = None

        try:
            if tvdb_id:
                result = lookup_series(tvdb_id=tvdb_id, session=session)
            else:
                result = lookup_series(name=search, session=session)
        except LookupError as e:
            return {'status': 'error',
                    'message': e.args[0]
                    }, 404

        return jsonify(result.to_dict())
