from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from future.utils import with_metaclass

import re

from flexget.config_schema import process_config


# TODO: rename all validator.valid -> validator.accepts / accepted / accept ?


class Errors(object):
    """Create and hold validator error messages."""

    def __init__(self):
        self.messages = []
        self.path = []
        self.path_level = None

    def count(self):
        """Return number of errors."""
        return len(self.messages)

    def add(self, msg):
        """Add new error message to current path."""
        path = [str(p) for p in self.path]
        msg = '[/%s] %s' % ('/'.join(path), msg)
        self.messages.append(msg)

    def back_out_errors(self, num=1):
        """Remove last num errors from list"""
        if num > 0:
            del self.messages[0 - num:]

    def path_add_level(self, value='?'):
        """Adds level into error message path"""
        self.path_level = len(self.path)
        self.path.append(value)

    def path_remove_level(self):
        """Removes level from path by depth number"""
        if self.path_level is None:
            raise Exception('no path level')
        del(self.path[self.path_level])
        self.path_level -= 1

    def path_update_value(self, value):
        """Updates path level value"""
        if self.path_level is None:
            raise Exception('no path level')
        self.path[self.path_level] = value

# A registry mapping validator names to their class
registry = {}


def factory(name='root', **kwargs):
    """Factory method, returns validator instance."""
    if name not in registry:
        raise Exception('Asked unknown validator \'%s\'' % name)
    return registry[name](**kwargs)


def any_schema(schemas):
    """
    Creates a schema that will match any of the given schemas.
    Will not use anyOf if there is just one validator in the list, for simpler error messages.

    """
    schemas = list(schemas)
    if len(schemas) == 1:
        return schemas[0]
    else:
        return {'anyOf': schemas}


class ValidatorType(type):
    """Automatically adds subclasses to the registry."""

    def __init__(cls, name, bases, dict):
        type.__init__(cls, name, bases, dict)
        if 'name' not in dict:
            raise Exception('Validator %s is missing class-attribute name' % name)
        registry[dict['name']] = cls


class Validator(with_metaclass(ValidatorType)):
    name = 'validator'

    def __init__(self, parent=None, message=None, **kwargs):
        self.valid = []
        self.message = message
        self.parent = parent
        self._errors = None

    @property
    def errors(self):
        """Recursively return the Errors class from the root of the validator tree."""
        if self.parent:
            return self.parent.errors
        else:
            if not self._errors:
                self._errors = Errors()
            return self._errors

    def add_root_parent(self):
        if self.name == 'root':
            return self
        root = factory('root')
        root.accept(self)
        return root

    def add_parent(self, parent):
        self.parent = parent
        return parent

    def get_validator(self, value, **kwargs):
        """Returns a child validator of this one.

        :param value:
          Can be a validator type string, an already created Validator instance,
          or a function that returns a validator instance.
        :param kwargs:
          Keyword arguments are passed on to validator init if a new validator is created.
        """
        if isinstance(value, Validator):
            # If we are passed a Validator instance, make it a child of this validator and return it.
            value.add_parent(self)
            return value
        elif callable(value):
            raise ValueError('lazy validators are no longer supported. Upgrade plugin to use new schema validation.')
        # Otherwise create a new child Validator
        kwargs['parent'] = self
        return factory(value, **kwargs)

    def accept(self, value, **kwargs):
        raise NotImplementedError('Validator %s should override accept method' % self.__class__.__name__)

    def schema(self):
        schema = self._schema()
        if self.message:
            schema['error'] = self.message
        return schema

    def _schema(self):
        """Return schema for validator"""
        raise NotImplementedError(self.__name__)

    def validate(self, value):
        """This is just to unit test backwards compatibility of json schema with old validators"""
        errors = list(e.message for e in process_config(value, self.schema()))
        self.errors.messages = errors
        return not errors

    def __str__(self):
        return '<validator:name=%s>' % self.name

    __repr__ = __str__


class RootValidator(Validator):
    name = 'root'

    def accept(self, value, **kwargs):
        v = self.get_validator(value, **kwargs)
        self.valid.append(v)
        return v

    def _schema(self):
        return any_schema([v.schema() for v in self.valid])


class ChoiceValidator(Validator):
    name = 'choice'

    def __init__(self, parent=None, **kwargs):
        self.valid_ic = []
        Validator.__init__(self, parent, **kwargs)

    def accept(self, value, ignore_case=False):
        """
        :param value: accepted text, int or boolean
        :param bool ignore_case: Whether case matters for text values
        """
        if not isinstance(value, (str, int, float)):
            raise Exception('Choice validator only accepts strings and numbers')
        if isinstance(value, str) and ignore_case:
            self.valid_ic.append(value.lower())
        else:
            self.valid.append(value)

    def accept_choices(self, values, **kwargs):
        """Same as accept but with multiple values (list)"""
        for value in values:
            self.accept(value, **kwargs)

    def _schema(self):
        schemas = []
        if self.valid:
            schemas.append({'enum': self.valid + self.valid_ic})
        if self.valid_ic:
            schemas.append(any_schema({"type": "string", "pattern": "(?i)^%s$" % p} for p in self.valid_ic))
        s = any_schema(schemas)
        s['error'] = 'Must be one of the following: %s' % ', '.join(map(str, self.valid + self.valid_ic))
        return s


class AnyValidator(Validator):
    name = 'any'

    def accept(self, value, **kwargs):
        self.valid = value

    def _schema(self):
        return {}


class EqualsValidator(Validator):
    name = 'equals'

    def accept(self, value, **kwargs):
        self.valid = value

    def _schema(self):
        return {'enum': [self.valid]}


class NumberValidator(Validator):
    name = 'number'

    def accept(self, name, **kwargs):
        pass

    def _schema(self):
        return {'type': 'number'}


class IntegerValidator(Validator):
    name = 'integer'

    def accept(self, name, **kwargs):
        pass

    def _schema(self):
        return {'type': 'integer'}


# TODO: Why would we need this instead of NumberValidator?
class DecimalValidator(Validator):
    name = 'decimal'

    def accept(self, name, **kwargs):
        pass

    def _schema(self):
        return {'type': 'number'}


class BooleanValidator(Validator):
    name = 'boolean'

    def accept(self, name, **kwargs):
        pass

    def _schema(self):
        return {'type': 'boolean'}


class TextValidator(Validator):
    name = 'text'

    def accept(self, name, **kwargs):
        pass

    def _schema(self):
        return {'type': 'string'}


class RegexpValidator(Validator):
    name = 'regexp'

    def accept(self, name, **kwargs):
        pass

    def _schema(self):
        return {'type': 'string', 'format': 'regex'}


class RegexpMatchValidator(Validator):
    name = 'regexp_match'

    def __init__(self, parent=None, **kwargs):
        Validator.__init__(self, parent, **kwargs)
        self.regexps = []
        self.reject_regexps = []

    def add_regexp(self, regexp_list, regexp):
        try:
            regexp_list.append(re.compile(regexp))
        except:
            raise ValueError('Invalid regexp given to match_regexp')

    def accept(self, regexp, **kwargs):
        self.add_regexp(self.regexps, regexp)
        if kwargs.get('message'):
            self.message = kwargs['message']

    def reject(self, regexp):
        self.add_regexp(self.reject_regexps, regexp)

    def _schema(self):
        schema = any_schema([{'type': 'string', 'pattern': regexp.pattern} for regexp in self.regexps])
        if self.reject_regexps:
            schema['not'] = any_schema([{'pattern': rej_regexp.pattern} for rej_regexp in self.reject_regexps])
        return schema


class IntervalValidator(RegexpMatchValidator):
    name = 'interval'

    def __init__(self, parent=None, **kwargs):
        RegexpMatchValidator.__init__(self, parent, **kwargs)
        self.accept(r'^\d+ (second|minute|hour|day|week)s?$')
        self.message = "should be in format 'x (seconds|minutes|hours|days|weeks)'"


class FileValidator(TextValidator):
    name = 'file'

    def validate(self, data):
        import os

        if not os.path.isfile(os.path.expanduser(data)):
            self.errors.add('File %s does not exist' % data)
            return False
        return True

    def _schema(self):
        return {'type': 'string', 'format': 'file'}


class PathValidator(TextValidator):
    name = 'path'

    def __init__(self, parent=None, allow_replacement=False, allow_missing=False, **kwargs):
        self.allow_replacement = allow_replacement
        self.allow_missing = allow_missing
        Validator.__init__(self, parent, **kwargs)

    def _schema(self):
        if self.allow_missing:
            return {'type': 'string'}
        return {'type': 'string', 'format': 'path'}


class UrlValidator(TextValidator):
    name = 'url'

    def __init__(self, parent=None, protocols=None, **kwargs):
        if protocols:
            self.protocols = protocols
        else:
            self.protocols = ['ftp', 'http', 'https', 'file']
        Validator.__init__(self, parent, **kwargs)

    def _schema(self):
        return {'type': 'string', 'format': 'url'}


class ListValidator(Validator):
    name = 'list'

    def accept(self, value, **kwargs):
        v = self.get_validator(value, **kwargs)
        self.valid.append(v)
        return v

    def _schema(self):
        return {'type': 'array', 'items': any_schema([v.schema() for v in self.valid])}


class DictValidator(Validator):
    name = 'dict'

    def __init__(self, parent=None, **kwargs):
        self.reject = {}
        self.any_key = []
        self.required_keys = []
        self.key_validators = []
        Validator.__init__(self, parent, **kwargs)
        # TODO: not dictionary?
        self.valid = {}

    def accept(self, value, key=None, required=False, **kwargs):
        """
        :param value: validator name, instance or function that returns an instance, which validates the given `key`
        :param string key: The dictionary key to accept
        :param bool required: = Mark this `key` as required
        :raises ValueError: `key` was not specified
        """
        if not key:
            raise ValueError('%s.accept() must specify key' % self.name)

        if required:
            self.require_key(key)

        v = self.get_validator(value, **kwargs)
        self.valid.setdefault(key, []).append(v)
        return v

    def reject_key(self, key, message=None):
        """Rejects a key"""
        self.reject[key] = message

    def reject_keys(self, keys, message=None):
        """Reject list of keys"""
        for key in keys:
            self.reject[key] = message

    def require_key(self, key):
        """Flag key as mandatory"""
        if key not in self.required_keys:
            self.required_keys.append(key)

    def accept_any_key(self, value, **kwargs):
        """Accepts any leftover keys in dictionary, which will be validated with `value`"""
        v = self.get_validator(value, **kwargs)
        self.any_key.append(v)
        return v

    def accept_valid_keys(self, value, key_type=None, key_validator=None, **kwargs):
        """
        Accepts keys that pass a given validator, and validates them using validator specified in `value`

        :param value: Validator name, instance or function returning an instance
            that will be used to validate dict values.
        :param key_type: Name of validator or list of names that determine which keys in this dict `value` will govern
        :param Validator key_validator: A validator instance that will be used to determine which keys in the dict
            `value` will govern
        :raises ValueError: If both `key_type` and `key_validator` are specified.
        """
        if key_type and key_validator:
            raise ValueError('key_type and key_validator are mutually exclusive')
        if key_validator:
            # Make sure errors show up in our list
            key_validator.add_parent(self)
        elif key_type:
            if isinstance(key_type, str):
                key_type = [key_type]
            key_validator = self.get_validator('root')
            for key_type in key_type:
                key_validator.accept(key_type)
        else:
            raise ValueError('%s.accept_valid_keys() must specify key_type or key_validator' % self.name)
        v = self.get_validator(value, **kwargs)
        self.key_validators.append((key_validator, v))
        return v

    def _schema(self):
        schema = {'type': 'object'}
        properties = schema['properties'] = {}
        for key, validators in self.valid.items():
            if not validators:
                continue
            properties[key] = any_schema(v.schema() for v in validators)
        if self.required_keys:
            schema['required'] = self.required_keys
        if self.any_key:
            schema['additionalProperties'] = any_schema([v.schema() for v in self.any_key])
        elif self.key_validators:
            # TODO: this doesn't actually validate keys
            schema['additionalProperties'] = any_schema(kv[1].schema() for kv in self.key_validators)
        else:
            schema['additionalProperties'] = False
        # TODO: implement this
        # if self.reject_keys:
        #     schema['reject_keys'] = self.reject

        return schema


class QualityValidator(TextValidator):
    name = 'quality'

    def _schema(self):
        return {'type': 'string', 'format': 'quality'}


class QualityRequirementsValidator(TextValidator):
    name = 'quality_requirements'

    def _schema(self):
        return {'type': 'string', 'format': 'qualityRequirements'}

# ---- TESTING ----


def build_options_validator(options):
    quals = ['720p', '1080p', '720p bluray', 'hdtv']
    options.accept('text', key='path')
    # set
    options.accept('dict', key='set').accept_any_key('any')
    # regexes can be given in as a single string ..
    options.accept('regexp', key='name_regexp')
    options.accept('regexp', key='ep_regexp')
    options.accept('regexp', key='id_regexp')
    # .. or as list containing strings
    options.accept('list', key='name_regexp').accept('regexp')
    options.accept('list', key='ep_regexp').accept('regexp')
    options.accept('list', key='id_regexp').accept('regexp')
    # quality
    options.accept('choice', key='quality').accept_choices(quals, ignore_case=True)
    options.accept('list', key='qualities').accept('choice').accept_choices(quals, ignore_case=True)
    options.accept('boolean', key='upgrade')
    options.accept('choice', key='min_quality').accept_choices(quals, ignore_case=True)
    options.accept('choice', key='max_quality').accept_choices(quals, ignore_case=True)
    # propers
    options.accept('boolean', key='propers')
    message = "should be in format 'x (minutes|hours|days|weeks)' e.g. '5 days'"
    time_regexp = r'\d+ (minutes|hours|days|weeks)'
    options.accept('regexp_match', key='propers', message=message + ' or yes/no').accept(time_regexp)
    # expect flags
    options.accept('choice', key='identified_by').accept_choices(['ep', 'id', 'auto'])
    # timeframe
    options.accept('regexp_match', key='timeframe', message=message).accept(time_regexp)
    # strict naming
    options.accept('boolean', key='exact')
    # watched in SXXEXX form
    watched = options.accept('regexp_match', key='watched')
    watched.accept('(?i)s\d\de\d\d$', message='Must be in SXXEXX format')
    # watched in dict form
    watched = options.accept('dict', key='watched')
    watched.accept('integer', key='season')
    watched.accept('integer', key='episode')
    # from group
    options.accept('text', key='from_group')
    options.accept('list', key='from_group').accept('text')
    # parse only
    options.accept('boolean', key='parse_only')


def complex_test():

    def build_list(series):
        """Build series list to series."""
        series.accept('text')
        series.accept('number')
        bundle = series.accept('dict')
        # prevent invalid indentation level
        """
        bundle.reject_keys(['set', 'path', 'timeframe', 'name_regexp',
            'ep_regexp', 'id_regexp', 'watched', 'quality', 'min_quality',
            'max_quality', 'qualities', 'exact', 'from_group'],
            'Option \'$key\' has invalid indentation level. It needs 2 more spaces.')
        """
        bundle.accept_any_key('path')
        options = bundle.accept_any_key('dict')
        build_options_validator(options)

    root = factory()

    # simple format:
    #   - series
    #   - another series

    simple = root.accept('list')
    build_list(simple)

    # advanced format:
    #   settings:
    #     group: {...}
    #   group:
    #     {...}

    """
    advanced = root.accept('dict')
    settings = advanced.accept('dict', key='settings')
    settings_group = settings.accept_any_key('dict')
    build_options_validator(settings_group)

    group = advanced.accept_any_key('list')
    build_list(group)
    """

    return root


if __name__ == '__main__':
    from flexget.plugins.input.rss import InputRSS
    # v = complex_test()
    v = InputRSS().validator()
    schema = v.schema()

    import json

    print(json.dumps(schema, sort_keys=True, indent=4))

    """
    root = factory()
    list = root.accept('list')
    list.accept('text')
    list.accept('regexp')
    list.accept('choice').accept_choices(['foo', 'bar'])

    print root.schema()
    """
