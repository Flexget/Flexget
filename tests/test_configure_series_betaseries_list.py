from unittest import mock

import pytest


def assert_mock_calls(expected_calls, mock_object):
    assert expected_calls == mock_object.mock_calls, (
        f"expecting calls {expected_calls!r}, got {mock_object.mock_calls!r} instead"
    )


def assert_series_count_in_db(expected_count):
    from flexget.components.series.db import Series
    from flexget.manager import Session

    session = Session()
    actual_series_count = session.query(Series).count()
    assert expected_count == actual_series_count, (
        f"expecting {expected_count} series stored in db, got {actual_series_count} instead"
    )


class TestConfigureSeriesBetaSeriesList:
    config = """
        tasks:
          test_no_members:
            configure_series:
              from:
                betaseries_list:
                  username: user_foo
                  password: passwd_foo
                  api_key: api_key_foo

          test_with_one_members:
            configure_series:
              from:
                betaseries_list:
                  username: user_foo
                  password: passwd_foo
                  api_key: api_key_foo
                  members:
                    - other_member_1

          test_with_two_members:
            configure_series:
              from:
                betaseries_list:
                  username: user_foo
                  password: passwd_foo
                  api_key: api_key_foo
                  members:
                    - other_member_1
                    - other_member_2
    """

    @pytest.fixture
    def create_token_mock(self, monkeypatch):
        # mock create_token
        the_mock = mock.Mock(return_value='token_foo')
        monkeypatch.setattr('flexget.plugins.input.betaseries_list.create_token', the_mock)
        return the_mock

    @pytest.fixture
    def query_series_mock(self, monkeypatch):
        # mock query_series
        the_mock = mock.Mock(return_value=[])
        monkeypatch.setattr('flexget.plugins.input.betaseries_list.query_series', the_mock)
        return the_mock

    def test_no_members(self, execute_task, create_token_mock, query_series_mock):
        query_series_mock.return_value = ["Breaking Bad", "Dexter"]

        execute_task('test_no_members')

        assert_series_count_in_db(2)
        assert_mock_calls([mock.call('api_key_foo', 'user_foo', 'passwd_foo')], create_token_mock)
        assert_mock_calls([mock.call('api_key_foo', 'token_foo', 'user_foo')], query_series_mock)

    def test_with_one_members(self, execute_task, create_token_mock, query_series_mock):
        query_series_mock.return_value = ["Breaking Bad", "Dexter", "The Simpsons"]

        execute_task('test_with_one_members')

        assert_series_count_in_db(3)
        assert_mock_calls([mock.call('api_key_foo', 'user_foo', 'passwd_foo')], create_token_mock)
        assert_mock_calls(
            [mock.call('api_key_foo', 'token_foo', 'other_member_1')], query_series_mock
        )

    def test_with_two_members(self, execute_task, create_token_mock, query_series_mock):
        return_values_generator = (
            val
            for val in [["Family guy", "The Simpsons"], ["Breaking Bad", "Dexter", "The Simpsons"]]
        )
        query_series_mock.side_effect = lambda *args: next(return_values_generator)

        execute_task('test_with_two_members')

        assert_series_count_in_db(4)
        assert_mock_calls([mock.call('api_key_foo', 'user_foo', 'passwd_foo')], create_token_mock)
        assert_mock_calls(
            [
                mock.call('api_key_foo', 'token_foo', 'other_member_1'),
                mock.call('api_key_foo', 'token_foo', 'other_member_2'),
            ],
            query_series_mock,
        )
