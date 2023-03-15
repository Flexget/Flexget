from flask import Response
from sqlalchemy.orm import Session

from flexget.api import APIResource, api
from flexget.api.app import base_message_schema, success_response

schema_api = api.namespace(
    'format_check', description='Test Flexget custom schema format validations'
)


class ObjectContainer:
    format_checker_input = {
        'type': 'object',
        'properties': {
            'quality': {'type': 'string', 'format': 'quality'},
            'quality_requirements': {'type': 'string', 'format': 'quality_requirements'},
            'time': {'type': 'string', 'format': 'time'},
            'interval': {'type': 'string', 'format': 'interval'},
            'size': {'type': 'string', 'format': 'size'},
            'percent': {'type': 'string', 'format': 'percent'},
            'regex': {'type': 'string', 'format': 'regex'},
            'file': {'type': 'string', 'format': 'file'},
            'path': {'type': 'string', 'format': 'path'},
            'url': {'type': 'string', 'format': 'url'},
            'episode_identifier': {'type': 'string', 'format': 'episode_identifier'},
            'episode_or_season_id': {'type': 'string', 'format': 'episode_or_season_id'},
        },
    }


format_checker_schema = api.schema_model('format_checker', ObjectContainer.format_checker_input)


@schema_api.route('/', doc=False)
class SchemaTest(APIResource):
    @api.validate(format_checker_schema)
    @api.response(200, model=base_message_schema)
    def post(self, session: Session = None) -> Response:
        """Validate flexget custom schema"""
        # If validation passed, all is well
        return success_response('payload is valid')
