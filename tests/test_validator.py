from flexget import validator
import yaml


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
        
    def test_regexp_match(self):
        re_match = validator.factory('regexp_match')
        re_match.accept('abc.*')
        assert not re_match.validate('foobar'), 'foobar should not have passed'
        assert re_match.validate('abcdefg'), 'abcdefg should have passed'
        
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
