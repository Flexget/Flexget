from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

from functools import wraps
from flask import request
from flask.helpers import make_response
from flexget.api.responses import PreconditionFailed, NotModified
from werkzeug.http import generate_etag


def etag(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        # Identify if this is a GET or HEAD in order to proceed
        assert request.method in ['HEAD', 'GET'], '@etag is only supported for GET requests'
        rv = f(*args, **kwargs)
        rv = make_response(rv)
        etag = generate_etag(rv.get_data())
        rv.headers['Cache-Control'] = 'max-age=86400'
        rv.headers['ETag'] = etag
        if_match = request.headers.get('If-Match')
        if_none_match = request.headers.get('If-None-Match')

        if if_match:
            etag_list = [tag.strip() for tag in if_match.split(',')]
            if etag not in etag_list and '*' not in etag_list:
                raise PreconditionFailed('etag does not match')
        elif if_none_match:
            etag_list = [tag.strip() for tag in if_none_match.split(',')]
            if etag in etag_list or '*' in etag_list:
                raise NotModified

        return rv

    return wrapped
