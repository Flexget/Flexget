from datetime import datetime
from flexget.utils import json


class TestJson(object):

    def test_dt_encode(self):
        date_str = '2016-03-11T17:12:17Z'
        dt = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%SZ')
        encoded_dt = json.dumps(dt, encode_datetime=True)
        assert encoded_dt == '"%s"' % date_str

    def test_dt_encode_obj(self):
        date_str = '2016-03-11T17:12:17Z'
        dt = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%SZ')
        date_obj = {'date': dt}
        encoded_dt = json.dumps(date_obj, encode_datetime=True)
        assert encoded_dt == '{"date": "%s"}' % date_str

    def test_dt_decode(self):
        date_str = '"2016-03-11T17:12:17Z"'
        dt = datetime.strptime(date_str, '"%Y-%m-%dT%H:%M:%SZ"')
        decoded_dt = json.loads(date_str, decode_datetime=True)
        assert dt == decoded_dt

    def test_dt_decode_obj(self):
        date_str = '"2016-03-11T17:12:17Z"'
        date_obj_str = '{"date": %s}' % date_str
        decoded_dt = json.loads(date_obj_str, decode_datetime=True)

        dt = datetime.strptime(date_str, '"%Y-%m-%dT%H:%M:%SZ"')
        assert decoded_dt == {'date': dt}
