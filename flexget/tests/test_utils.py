import math
from datetime import datetime

import pytest

from flexget.utils import json
from flexget.utils.tools import parse_filesize, split_title_year


def compare_floats(float1, float2):
    eps = 0.0001
    return math.fabs(float1 - float2) <= eps


class TestJson:
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


class TestParseFilesize:
    def test_parse_filesize_no_space(self):
        size = '200KB'
        expected = 200 * 1000 / 1024 ** 2
        assert compare_floats(parse_filesize(size), expected)

    def test_parse_filesize_space(self):
        size = '200.0 KB'
        expected = 200 * 1000 / 1024 ** 2
        assert compare_floats(parse_filesize(size), expected)

    def test_parse_filesize_non_si(self):
        size = '1234 GB'
        expected = 1234 * 1000 ** 3 / 1024 ** 2
        assert compare_floats(parse_filesize(size), expected)

    def test_parse_filesize_auto(self):
        size = '1234 GiB'
        expected = 1234 * 1024 ** 3 / 1024 ** 2
        assert compare_floats(parse_filesize(size), expected)

    def test_parse_filesize_auto_mib(self):
        size = '1234 MiB'
        assert compare_floats(parse_filesize(size), 1234)

    def test_parse_filesize_ib_not_valid(self):
        with pytest.raises(ValueError):
            parse_filesize('100 ib')

    def test_parse_filesize_single_digit(self):
        size = '1 GiB'
        assert compare_floats(parse_filesize(size), 1024)

    def test_parse_filesize_separators(self):
        size = '1,234 GiB'
        assert parse_filesize(size) == 1263616

        size = '1 234 567 MiB'
        assert parse_filesize(size) == 1234567


class TestSplitYearTitle:
    @pytest.mark.parametrize(
        'title, expected_title, expected_year',
        [
            ('The Matrix', 'The Matrix', None),
            ('The Matrix 1999', 'The Matrix', 1999),
            ('The Matrix (1999)', 'The Matrix', 1999),
            ('The Matrix - 1999', 'The Matrix -', 1999),
            ('The.Matrix.1999', 'The.Matrix.', 1999),
            (
                'The Human Centipede III (Final Sequence)',
                'The Human Centipede III (Final Sequence)',
                None,
            ),
            (
                'The Human Centipede III (Final Sequence) (2015)',
                'The Human Centipede III (Final Sequence)',
                2015,
            ),
            ('2020', '2020', None),
        ],
    )
    def test_split_year_title(self, title, expected_title, expected_year):
        assert split_title_year(title) == (expected_title, expected_year)
