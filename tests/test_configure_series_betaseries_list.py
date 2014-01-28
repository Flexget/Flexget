from __future__ import unicode_literals, division, absolute_import
from mock import patch, call
from tests import FlexGetBase
import flexget.plugins.input.betaseries_list


def assert_mock_calls(expected_calls, mock_object):
    assert expected_calls == mock_object.mock_calls, "expecting calls %r, got %r instead" % \
                                                     (expected_calls, mock_object.mock_calls)


def assert_series_count_in_db(expected_count):
    from flexget.plugins.filter.series import Series
    from flexget.manager import Session
    session = Session()
    actual_series_count = session.query(Series).count()
    assert expected_count == actual_series_count, "expecting %s series stored in db, got %s instead" % \
                                                  (expected_count, actual_series_count)


class Test_configure_series_betaseries_list(FlexGetBase):

    __yaml__ = """
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

    def setup(self):
        super(Test_configure_series_betaseries_list, self).setup()
        ## mock create_token
        self.create_token_patcher = patch.object(flexget.plugins.input.betaseries_list, "create_token",
                                                 return_value='token_foo')
        self.create_token_mock = self.create_token_patcher.start()

        ## mock query_series
        self.query_series_patcher = patch.object(flexget.plugins.input.betaseries_list, "query_series",
                                                 return_value=[])
        self.query_series_mock = self.query_series_patcher.start()

    def teardown(self):
        super(Test_configure_series_betaseries_list, self).teardown()
        self.create_token_patcher.stop()
        self.query_series_patcher.stop()

    def test_no_members(self):
        # GIVEN
        self.query_series_mock.return_value = ["Breaking Bad", "Dexter"]
        # WHEN
        self.execute_task('test_no_members')
        # THEN
        assert_series_count_in_db(2)
        assert_mock_calls([call('api_key_foo', 'user_foo', 'passwd_foo')],  self.create_token_mock)
        assert_mock_calls([call('api_key_foo', 'token_foo', 'user_foo')], self.query_series_mock)

    def test_with_one_members(self):
        # GIVEN
        self.query_series_mock.return_value = ["Breaking Bad", "Dexter", "The Simpsons"]
        # WHEN
        self.execute_task('test_with_one_members')
        # THEN
        assert_series_count_in_db(3)
        assert_mock_calls([call('api_key_foo', 'user_foo', 'passwd_foo')],  self.create_token_mock)
        assert_mock_calls([call('api_key_foo', 'token_foo', 'other_member_1')], self.query_series_mock)

    def test_with_two_members(self):
        # GIVEN
        return_values_generator = (val for val in [
            ["Family guy", "The Simpsons"],
            ["Breaking Bad", "Dexter", "The Simpsons"],
        ])
        self.query_series_mock.side_effect = lambda *args: return_values_generator.next()
        # WHEN
        self.execute_task('test_with_two_members')
        # THEN
        assert_series_count_in_db(4)
        assert_mock_calls([call('api_key_foo', 'user_foo', 'passwd_foo')],  self.create_token_mock)
        assert_mock_calls(
            [
                call('api_key_foo', 'token_foo', 'other_member_1'),
                call('api_key_foo', 'token_foo', 'other_member_2')
            ], self.query_series_mock)
