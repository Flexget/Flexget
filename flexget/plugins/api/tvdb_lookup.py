from __future__ import unicode_literals, division, absolute_import

try:
    from xml.etree.ElementTree import ParseError
except ImportError:
    # Python 2.6 throws this instead when there is invalid xml
    from xml.parsers.expat import ExpatError as ParseError

from flask import jsonify
from flexget.plugins.api_tvdb import lookup_series

from flexget.api import api, APIResource

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
