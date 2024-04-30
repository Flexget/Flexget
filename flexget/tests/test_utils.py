from datetime import datetime

import pytest

from flexget.utils import json
from flexget.utils.tools import merge_dict_from_to, parse_filesize, split_title_year


class TestJson:
    def test_json_encode_dt(self):
        date_str = '2016-03-11T17:12:17Z'
        dt = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%SZ')
        encoded_dt = json.dumps(dt, encode_datetime=True)
        assert encoded_dt == f'"{date_str}"'

    def test_json_encode_dt_dict(self):
        date_str = '2016-03-11T17:12:17Z'
        dt = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%SZ')
        date_obj = {'date': dt}
        encoded_dt = json.dumps(date_obj, encode_datetime=True)
        assert encoded_dt == f'{{"date": "{date_str}"}}'

    def test_json_decode_dt(self):
        date_str = '"2016-03-11T17:12:17Z"'
        dt = datetime.strptime(date_str, '"%Y-%m-%dT%H:%M:%SZ"')
        decoded_dt = json.loads(date_str, decode_datetime=True)
        assert dt == decoded_dt

    def test_json_decode_dt_obj(self):
        date_str = '"2016-03-11T17:12:17Z"'
        date_obj_str = f'{{"date": {date_str}}}'
        decoded_dt = json.loads(date_obj_str, decode_datetime=True)

        dt = datetime.strptime(date_str, '"%Y-%m-%dT%H:%M:%SZ"')
        assert decoded_dt == {'date': dt}


class TestParseFilesize:
    @pytest.mark.parametrize(
        'size_text, expected',
        [
            ('200KB', 200 * 1000),
            ('200.0 KB', 200 * 1000),
            ('1234 GB', 1234 * 1000**3),
            ('1234 GB', 1234 * 1000**3),
            ('1234 GiB', 1234 * 1024**3),
            ('1234 MiB', 1234 * 1024**2),
            ('1 GiB', 1024**3),
            ('1,234 GiB', 1234 * 1024**3),
            ('1 234 567 MiB', 1234567 * 1024**2),
        ],
    )
    def test_parse_filesize(self, size_text, expected):
        assert parse_filesize(size_text) == pytest.approx(expected)

    def test_parse_filesize_ib_not_valid(self):
        with pytest.raises(ValueError):
            parse_filesize('100 ib')


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


class TestDictMerge:
    def test_merge_dict_to_dict_list(self):
        d1 = {'setting': {'parameter': ['item_1']}}
        d2 = {'setting': {'parameter': ['item_2']}}
        merge_dict_from_to(d1, d2)
        assert d2 == {'setting': {'parameter': ['item_2', 'item_1']}}

    def test_merge_dict_to_dict_override(self):
        d1 = {'setting': {'parameter': ['item_1']}}
        d2 = {'setting': {'parameter': 2}}
        merge_dict_from_to(d1, d2)
        assert d2 == {'setting': {'parameter': 2}}

    def test_merge_dict_to_dict_add(self):
        d1 = {'setting': {'parameter_1': ['item_1']}}
        d2 = {'setting': {'parameter_2': 'item_2'}}
        merge_dict_from_to(d1, d2)
        assert d2 == {'setting': {'parameter_1': ['item_1'], 'parameter_2': 'item_2'}}

    def test_merge_dict_to_dict_str(self):
        d1 = {'setting': {'parameter': 'item_1'}}
        d2 = {'setting': {'parameter': 'item_2'}}
        merge_dict_from_to(d1, d2)
        assert d2 == {'setting': {'parameter': 'item_2'}}

    def test_merge_list_to_list(self):
        d1 = {'setting': ['item_1']}
        d2 = {'setting': ['item_2']}
        merge_dict_from_to(d1, d2)
        assert d2 == {'setting': ['item_2', 'item_1']}

    def test_merge_list_to_str(self):
        d1 = {'setting': ['list']}
        d2 = {'setting': 'string'}
        merge_dict_from_to(d1, d2)
        assert d2 == {'setting': 'string'}

    def test_merge_str_to_list(self):
        d1 = {'setting': 'string'}
        d2 = {'setting': ['list']}
        merge_dict_from_to(d1, d2)
        assert d2 == {'setting': ['list']}

    def test_merge_str_to_str(self):
        d1 = {'setting': 'string_1'}
        d2 = {'setting': 'string_2'}
        merge_dict_from_to(d1, d2)
        assert d2 == {'setting': 'string_2'}
