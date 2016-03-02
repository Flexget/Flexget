"""
These validate methods are never run by FlexGet anymore, but these tests serve as a sanity check that the
old validators will get converted to new schemas properly for plugins still using the `validator` method.
"""
from __future__ import unicode_literals, division, absolute_import

from flexget import validator
from tests.util import maketemp

class TestValidator(object):

    def test_default(self):
        root = validator.factory()
        assert root.name == 'root', 'expected root'
        dv = root.accept('dict')
        assert dv.name == 'dict', 'expected dict'
        dv.accept('text', key='text')

    def test_dict(self):
        dv = validator.factory('dict')
        dv.accept('dict', key='foo')
        result = dv.validate({'foo': {}})
        assert not dv.errors.messages, 'should have passed foo'
        assert result, 'invalid result for foo'
        result = dv.validate({'bar': {}})
        assert dv.errors.messages, 'should not have passed bar'
        assert not result, 'should have an invalid result for bar'
        # Test validation of dictionary keys
        dv = validator.factory('dict')
        dv.accept_valid_keys('dict', key_type='number')
        result = dv.validate({3: {}})
        assert not dv.errors.messages, 'should have passed 3'
        assert result, 'invalid result for key 3'
        # Json schema cannot do key validation
        """result = dv.validate({'three': {}})
        assert dv.errors.messages, 'should not have passed three'
        assert not result, 'should have an invalid result for 3'"""

    def test_regexp_match(self):
        re_match = validator.factory('regexp_match')
        re_match.accept('abc.*')
        assert not re_match.validate('foobar'), 'foobar should not have passed'
        assert re_match.validate('abcdefg'), 'abcdefg should have passed'

    def test_interval(self):
        interval = validator.factory('interval')
        assert interval.validate('3 days')
        assert interval.validate('12 hours')
        assert interval.validate('1 minute')

        assert not interval.validate('aoeu')
        assert not interval.validate('14')
        assert not interval.validate('3 dayz')
        assert not interval.validate('about 5 minutes')

    def test_choice(self):
        choice = validator.factory('choice')
        choice.accept('foo')
        choice.accept('Bar', ignore_case=True)
        choice.accept(120)
        choice.validate('foo')
        print choice.errors.messages
        assert not choice.errors.messages, 'foo should be valid'
        choice.validate(120)
        print choice.errors.messages
        assert not choice.errors.messages, '120 should be valid'
        choice.validate('bAR')
        print choice.errors.messages
        assert not choice.errors.messages, 'bAR should be valid'
        choice.validate('xxx')
        print choice.errors.messages
        assert choice.errors.messages, 'xxx should be invalid'
        choice.errors.messages = []
        choice.validate(300)
        print choice.errors.messages
        assert choice.errors.messages, '300 should be invalid'
        choice.errors.messages = []
        choice.validate('fOO')
        print choice.errors.messages
        assert choice.errors.messages, 'fOO should be invalid'

    # This validator is not supported with json schema
    def _lazy(self):
        """Test lazy validators by making a recursive one."""

        def recursive_validator():
            root = validator.factory('dict')
            root.accept('integer', key='int')
            root.accept(recursive_validator, key='recurse')
            return root

        test_config = {'int': 1,
                       'recurse': {
                           'int': 2,
                           'recurse': {
                               'int': 3}}}

        assert recursive_validator().validate(test_config), 'Config should pass validation'
        test_config['recurse']['badkey'] = 4
        assert not recursive_validator().validate(test_config), 'Config should not be valid'

    def test_path(self):
        path = validator.factory('path')
        path_allow_missing = validator.factory('path', allow_missing=True)
        temp_path = maketemp()
        path.validate(temp_path)
        print path.errors.messages
        assert not path.errors.messages, '%s should be valid' % (temp_path)
        path_allow_missing.validate('missing_directory')
        print path_allow_missing.errors.messages
        assert not path_allow_missing.errors.messages, 'missing_directory should be valid with allow_missing'
        path.validate('missing_directory')
        print path.errors.messages
        assert path.errors.messages, 'missing_directory should be invalid'
        path_allow_missing.errors.messages = []
