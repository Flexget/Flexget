from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

from datetime import datetime

from flexget.utils import json


class TestJson(object):

    def test_json_encode_dt(self):
        date_str = '2016-03-11T17:12:17Z'
        dt = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%SZ')
        encoded_dt = json.dumps(dt, encode_datetime=True)
        assert encoded_dt == '"%s"' % date_str

    def test_json_encode_dt_dict(self):
        date_str = '2016-03-11T17:12:17Z'
        dt = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%SZ')
        date_obj = {'date': dt}
        encoded_dt = json.dumps(date_obj, encode_datetime=True)
        assert encoded_dt == '{"date": "%s"}' % date_str

    def test_json_decode_dt(self):
        date_str = '"2016-03-11T17:12:17Z"'
        dt = datetime.strptime(date_str, '"%Y-%m-%dT%H:%M:%SZ"')
        decoded_dt = json.loads(date_str, decode_datetime=True)
        assert dt == decoded_dt

    def test_json_decode_dt_obj(self):
        date_str = '"2016-03-11T17:12:17Z"'
        date_obj_str = '{"date": %s}' % date_str
        decoded_dt = json.loads(date_obj_str, decode_datetime=True)

        dt = datetime.strptime(date_str, '"%Y-%m-%dT%H:%M:%SZ"')
        assert decoded_dt == {'date': dt}
