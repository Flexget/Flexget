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


def factory(name='root'):
    """Factory method, returns validator instance."""
    v = Validator()
    return v.get_validator(name)


class Validator(object):

    name = 'validator'

    def __init__(self, parent=None):
        self.valid = []
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

    def get_validator(self, name):
        if not self.validators.get(name):
            raise Exception('Asked unknown validator \'%s\'' % name)
        #print 'returning %s' % name
        return self.validators[name](self)

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
            #print 'validating %s' % rule.name
            if rule.validateable(item):
                if rule.validate(item):
                    return True
        # If no validators matched or reported errors, and one of them has a custom error message, display it.
        if count == self.errors.count():
            for rule in rules:
                if hasattr(rule, 'message') and rule.message:
                    self.errors.add(rule.message)
        return False

    def __str__(self):
        return '<%s>' % self.name
        

class RootValidator(Validator):
    name = 'root'

    def accept(self, name, **kwargs):
        v = self.get_validator(name)
        self.valid.append(v)
        return v
    
    def validateable(self, data):
        return True
    
    def validate(self, data):
        count = self.errors.count()
        for v in self.valid:
            if v.validateable(data):
                if v.validate(data):
                    return True
        # containers should only add errors if inner validators did not
        if count == self.errors.count():
            acceptable = [v.name for v in self.valid]
            self.errors.add('failed to pass as %s' % ', '.join(acceptable))
        return False


class ChoiceValidator(Validator):
    name = 'choice'

    def __init__(self, parent=None):
        self.valid_ic = []
        Validator.__init__(self, parent)

    def accept(self, value, **kwargs):
        if not isinstance(value, basestring):
            raise Exception('Choice validator only accepts strings')
        if kwargs.get('ignore_case'):
            self.valid_ic.append(value.lower())
        else:        
            self.valid.append(value)
        
    def accept_choices(self, values, **kwargs):
        for value in values:
            self.accept(value, **kwargs)

    def validateable(self, data):
        return isinstance(data, basestring)

    def validate(self, data):
        if data in self.valid or data.lower() in self.valid_ic:
            return True
        else:
            self.errors.add('must be one of values %s' % ', '.join(self.valid + self.valid_ic))
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
        from numbers import Number as number
        return isinstance(data, basestring) or isinstance(data, number)
    
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

    def __init__(self, parent=None):
        self.regexps = []
        self.message = None
        Validator.__init__(self, parent)
    
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
    
    def validate(self, data):
        import os
        if not os.path.isdir(os.path.expanduser(data)):
            self.errors.add('Path %s does not exist' % data)
            return False
        return True


class UrlValidator(TextValidator):
    name = 'url'
    
    def validate(self, data):
        regexp = '(ftp|http|https):\/\/(\w+:{0,1}\w*@)?(\S+)(:[0-9]+)?(\/|\/([\w#!:.?+=&%@!\-\/]))?'
        if not isinstance(data, basestring):
            self.errors.add('expecting text')
            return False
        valid = re.match(regexp, data) != None
        if not valid:
            self.errors.add('value %s is not a valid url' % data)
        return valid
        

class ListValidator(Validator):
    name = 'list'

    def accept(self, name, **kwargs):
        v = self.get_validator(name)
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
            if not self.validate_item(item, self.valid):
                # containers should only add errors if inner validators did not
                if count == self.errors.count():
                    l = [r.name for r in self.valid]
                    self.errors.add('is not valid %s' % (', '.join(l)))
        self.errors.path_remove_level()
        return count == self.errors.count()


class DictValidator(Validator):
    name = 'dict'

    def __init__(self, parent=None):
        self.reject = {}
        self.any_key = []
        self.required_keys = []
        Validator.__init__(self, parent)
        # TODO: not dictionary?
        self.valid = {}

    def accept(self, name, **kwargs):
        """Accepts key with name type"""
        if not 'key' in kwargs:
            raise Exception('%s.accept() must specify key' % self.name)

        key = kwargs['key']
        v = self.get_validator(name)
        self.valid.setdefault(key, []).append(v)
        # complain from old format
        if 'require' in kwargs:
            print 'Deprecated validator api, should use required=bool instead of require=bool'
        if kwargs.get('required', False):
            self.require_key(key)
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
        v = self.get_validator(name)
        #v.accept(name, **kwargs)
        self.any_key.append(v)
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
            if not key in self.valid and not self.any_key:
                self.errors.add('key \'%s\' is not recognized' % key)
                continue
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
            # rules contain rules specified for this key AND
            # rules specified for any key
            rules = self.valid.get(key, [])
            rules.extend(self.any_key)
            if not self.validate_item(value, rules):
                # containers should only add errors if inner validators did not
                if count == self.errors.count():
                    l = [r.name for r in rules]
                    self.errors.add('value \'%s\' is not valid %s' % (value, ', '.join(l)))
        for required in self.required_keys:
            if not required in data:
                self.errors.add('key \'%s\' required' % required)
        self.errors.path_remove_level()
        return count == self.errors.count()


if __name__ == '__main__':
    root = factory()
