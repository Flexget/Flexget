import re

# TODO: rename all validator.valid -> validator.accepts / accepted / accept ?


class Errors:

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


def factory(name='root', **kwargs):
    """Factory method, returns validator instance."""
    v = Validator()
    return v.get_validator(name, **kwargs)


class Validator(object):

    name = 'validator'

    def __init__(self, parent=None, message=None, **kwargs):
        self.valid = []
        self.message = message
        if parent is None:
            self.errors = Errors()
            self.validators = {}

            # register default validators
            register = [RootValidator, ListValidator, DictValidator, TextValidator, FileValidator,
                        PathValidator, AnyValidator, NumberValidator, BooleanValidator, RegexpMatchValidator,
                        DecimalValidator, UrlValidator, RegexpValidator, EqualsValidator, ChoiceValidator]
            for v in register:
                self.register(v)
        else:
            self.errors = parent.errors
            self.validators = parent.validators

    def register(self, validator):
        if not hasattr(validator, 'name'):
            raise Exception('Validator %s is missing class-attribute name' % validator.__class__.__name__)
        self.validators[validator.name] = validator

    def add_root_parent(self):
        if self.name == 'root':
            return self
        validator = self.get_validator('root')
        validator.errors = self.errors
        validator.validators = self.validators
        validator.valid.append(self)
        self.parent = validator
        return validator

    def get_validator(self, name, **kwargs):
        if not self.validators.get(name):
            raise Exception('Asked unknown validator \'%s\'' % name)
        # print 'returning %s' % name
        return self.validators[name](self, **kwargs)

    def accept(self, name, **kwargs):
        raise Exception('Validator %s should override accept method' % self.__class__.__name__)

    def validateable(self, data):
        """Return True if validator can be used to validate given data, False otherwise."""
        raise Exception('Validator %s should override validateable method' % self.__class__.__name__)

    def validate(self, data):
        """Validate given data and log errors, return True if passed and False if not."""
        raise Exception('Validator %s should override validate method' % self.__class__.__name__)

    def validate_item(self, item, rules):
        """
            Helper method. Validate item against list of rules (validators).
            Return True if item passed any of the rules, False if none of the rules pass item.
        """
        count = self.errors.count()
        for rule in rules:
            # print 'validating %s' % rule.name
            if rule.validateable(item):
                if rule.validate(item):
                    # item is valid, remove added errors before returning
                    self.errors.back_out_errors(self.errors.count() - count)
                    return True

        # If no validators matched or reported errors, and one of them has a custom error message, display it.
        if count == self.errors.count():
            for rule in rules:
                if rule.message:
                    self.errors.add(rule.message)
            # If there are still no errors, list the valid types, as well as what was actually received
            if count == self.errors.count():
                acceptable = [v.name for v in rules]
                # Make acceptable into an english list, with commas and 'or'
                acceptable = ', '.join(acceptable[:-2] + ['']) + ' or '.join(acceptable[-2:])
                self.errors.add('must be a %s value' % acceptable)
                if isinstance(item, dict):
                    self.errors.add('got a dict instead of %s' % acceptable)
                elif isinstance(item, list):
                    self.errors.add('got a list instead of %s' % acceptable)
                else:
                    self.errors.add('value \'%s\' is not valid %s' % (item, acceptable))
        return False

    def __str__(self):
        return '<%s>' % self.name


class RootValidator(Validator):
    name = 'root'

    def accept(self, name, **kwargs):
        v = self.get_validator(name, **kwargs)
        self.valid.append(v)
        return v

    def validateable(self, data):
        return True

    def validate(self, data):
        count = self.errors.count()
        return self.validate_item(data, self.valid)


class ChoiceValidator(Validator):
    name = 'choice'

    def __init__(self, parent=None, **kwargs):
        self.valid_ic = []
        Validator.__init__(self, parent, **kwargs)

    def accept(self, value, **kwargs):
        if not isinstance(value, (basestring, int, float)):
            raise Exception('Choice validator only accepts strings and numbers')
        if isinstance(value, basestring) and kwargs.get('ignore_case'):
            self.valid_ic.append(value.lower())
        else:
            self.valid.append(value)

    def accept_choices(self, values, **kwargs):
        for value in values:
            self.accept(value, **kwargs)

    def validateable(self, data):
        return isinstance(data, (basestring, int, float))

    def validate(self, data):
        if data in self.valid:
            return True
        elif isinstance(data, basestring) and data.lower() in self.valid_ic:
            return True
        else:
            acceptable = [str(value) for value in self.valid + self.valid_ic]
            self.errors.add('\'%s\' is not one of acceptable values: %s' % (data, ', '.join(acceptable)))
            return False


class AnyValidator(Validator):
    name = 'any'

    def accept(self, value, **kwargs):
        self.valid = value

    def validateable(self, data):
        return True

    def validate(self, data):
        return True


class EqualsValidator(Validator):
    name = 'equals'

    def accept(self, value, **kwargs):
        self.valid = value

    def validateable(self, data):
        return isinstance(data, (basestring, int, float))

    def validate(self, data):
        return self.valid == data


class NumberValidator(Validator):
    name = 'number'

    def accept(self, name, **kwargs):
        pass

    def validateable(self, data):
        return isinstance(data, int)

    def validate(self, data):
        valid = isinstance(data, int)
        if not valid:
            self.errors.add('value %s is not valid number' % data)
        return valid


class BooleanValidator(Validator):
    name = 'boolean'

    def accept(self, name, **kwargs):
        pass

    def validateable(self, data):
        return isinstance(data, bool)

    def validate(self, data):
        valid = isinstance(data, bool)
        if not valid:
            self.errors.add('value %s is not valid boolean' % data)
        return valid


class DecimalValidator(Validator):
    name = 'decimal'

    def accept(self, name, **kwargs):
        pass

    def validateable(self, data):
        return isinstance(data, float)

    def validate(self, data):
        valid = isinstance(data, float)
        if not valid:
            self.errors.add('value %s is not valid decimal number' % data)
        return valid


class TextValidator(Validator):
    name = 'text'

    def accept(self, name, **kwargs):
        pass

    def validateable(self, data):
        return isinstance(data, basestring)

    def validate(self, data):
        valid = isinstance(data, basestring)
        if not valid:
            self.errors.add('value %s is not valid text' % data)
        return valid


class RegexpValidator(Validator):
    name = 'regexp'

    def accept(self, name, **kwargs):
        pass

    def validateable(self, data):
        return isinstance(data, basestring)

    def validate(self, data):
        if not isinstance(data, basestring):
            self.errors.add('Value should be text')
            return False
        try:
            re.compile(data)
        except:
            self.errors.add('%s is not a valid regular expression' % data)
            return False
        return True


class RegexpMatchValidator(Validator):
    name = 'regexp_match'

    def __init__(self, parent=None, **kwargs):
        self.regexps = []
        Validator.__init__(self, parent, **kwargs)

    def accept(self, regexp, **kwargs):
        try:
            self.regexps.append(re.compile(regexp))
        except:
            raise Exception('Invalid regexp given to match_regexp')
        if kwargs.get('message'):
            self.message = kwargs['message']

    def validateable(self, data):
        return isinstance(data, basestring)

    def validate(self, data):
        if not isinstance(data, basestring):
            self.errors.add('Value should be text')
            return False
        for regexp in self.regexps:
            if regexp.match(data):
                return True
        if self.message:
            self.errors.add(self.message)
        else:
            self.errors.add('%s does not match regexp' % data)
        return False


class FileValidator(TextValidator):
    name = 'file'

    def validate(self, data):
        import os

        if not os.path.isfile(os.path.expanduser(data)):
            self.errors.add('File %s does not exist' % data)
            return False
        return True


class PathValidator(TextValidator):
    name = 'path'

    def __init__(self, parent=None, allow_replacement=False, **kwargs):
        self.allow_replacement = allow_replacement
        Validator.__init__(self, parent, **kwargs)

    def validate(self, data):
        import os

        path = data
        if self.allow_replacement:
            # If string replacement is allowed, only validate the part of the
            # path before the first identifier to be replaced
            pat = re.compile(r'''
                %                     # Start with percent,
                (?:\( ([^()]*) \))    # name in parens (do not capture parens),
                [-+ #0]*              # zero or more flags
                (?:\*|[0-9]*)         # optional minimum field width
                (?:\.(?:\*|[0-9]*))?  # optional dot and length modifier
                [EGXcdefgiorsux%]     # type code (or [formatted] percent character)
                ''', re.VERBOSE)

            result = pat.search(data)
            if result:
                path = os.path.dirname(data[0:result.start()])

        if not os.path.isdir(os.path.expanduser(path)):
            self.errors.add('Path %s does not exist' % path)
            return False
        return True


class UrlValidator(TextValidator):
    name = 'url'

    def __init__(self, parent=None, **kwargs):
        self.protocols = ['ftp', 'http', 'https']
        if 'protocols' in kwargs:
            self.protocols = kwargs['protocols']
        Validator.__init__(self, parent, **kwargs)

    def validate(self, data):
        regexp = '(' + '|'.join(self.protocols) + '):\/\/(\w+:{0,1}\w*@)?(\S+)(:[0-9]+)?(\/|\/([\w#!:.?+=&%@!\-\/]))?'
        if not isinstance(data, basestring):
            self.errors.add('expecting text')
            return False
        valid = re.match(regexp, data) is not None
        if not valid:
            self.errors.add('value %s is not a valid url' % data)
        return valid


class ListValidator(Validator):
    name = 'list'

    def accept(self, name, **kwargs):
        v = self.get_validator(name, **kwargs)
        self.valid.append(v)
        return v

    def validateable(self, data):
        return isinstance(data, list)

    def validate(self, data):
        if not isinstance(data, list):
            self.errors.add('value must be a list')
            return False
        self.errors.path_add_level()
        count = self.errors.count()
        for item in data:
            self.errors.path_update_value('list:%i' % data.index(item))
            self.validate_item(item, self.valid)
        self.errors.path_remove_level()
        return count == self.errors.count()


class DictValidator(Validator):
    name = 'dict'

    def __init__(self, parent=None, **kwargs):
        self.reject = {}
        self.any_key = []
        self.required_keys = []
        self.validated_keys = {}
        Validator.__init__(self, parent, **kwargs)
        # TODO: not dictionary?
        self.valid = {}

    def accept(self, name, **kwargs):
        """Accepts key with name type"""
        if not 'key' in kwargs:
            raise Exception('%s.accept() must specify key' % self.name)

        key = kwargs['key']
        # complain from old format
        if 'require' in kwargs:
            print 'Deprecated validator api, should use required=bool instead of require=bool'
        if kwargs.get('required', False):
            self.require_key(key)
        # clean our keys from kwargs, so they can be passed to Validator constuctor
        for k in ['key', 'require', 'required']:
            if k in kwargs:
                del kwargs[k]
        v = self.get_validator(name, **kwargs)
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
        if not key in self.required_keys:
            self.required_keys.append(key)

    def accept_any_key(self, name, **kwargs):
        """Accepts any key with given type"""
        v = self.get_validator(name, **kwargs)
        # v.accept(name, **kwargs)
        self.any_key.append(v)
        return v

    def accept_valid_keys(self, name, **kwargs):
        """Accepts key with name type"""
        if not 'key_type' in kwargs:
            raise Exception('%s.accept_valid_keys() must specify key_type' % self.name)
        key_types = kwargs['key_type']
        if isinstance(key_types, basestring):
            key_types = [key_types]
        v = self.get_validator(name, **kwargs)
        for key_type in key_types:
            self.validated_keys.setdefault(key_type, []).append(v)
        return v

    def validateable(self, data):
        return isinstance(data, dict)

    def validate(self, data):
        if not isinstance(data, dict):
            self.errors.add('value must be a dictionary')
            return False

        count = self.errors.count()
        self.errors.path_add_level()
        for key, value in data.iteritems():
            self.errors.path_update_value('dict:%s' % key)
            # reject keys
            if key in self.reject:
                msg = self.reject[key]
                if msg:
                    from string import Template
                    template = Template(msg)
                    self.errors.add(template.safe_substitute(key=key))
                else:
                    self.errors.add('key \'%s\' is forbidden here' % key)
                continue
            # Get rules for key, most specific rules will be used
            rules = []
            if key in self.valid:
                # Rules for explicitly allowed keys
                rules = self.valid.get(key, [])
            else:
                for v_type in self.validated_keys:
                    v = self.get_validator(v_type)
                    if v.validateable(key) and v.validate(key):
                        # Rules for a validated_key
                        rules = self.validated_keys[v_type]
                        break
                else:
                    if self.any_key:
                        # Rules for any key
                        rules = self.any_key
            if not rules:
                self.errors.add('key \'%s\' is not recognized' % key)
                # TODO: print the valid options
                continue
            self.validate_item(value, rules)
        self.errors.path_remove_level()
        for required in self.required_keys:
            if not required in data:
                self.errors.add('key \'%s\' required' % required)
        return count == self.errors.count()


if __name__ == '__main__':
    root = factory()
