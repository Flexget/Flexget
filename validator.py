import re

# TODO: "validation succeeded, errors are logged so it's considered clean!"
# TODO: rename all validator.valid -> validator.accepts / accepted / accept ?
# TODO: path validator

class Errors:

    """Create and hold validator error messages."""

    def __init__(self):
        self.messages = []
        self.path = []
        self.path_level = None
        self.frozen = False
        
    def freeze(self):
        self.frozen = True
        
    def unfreeze(self):
        self.frozen = False
        
    def count(self):
        """Return number of errors"""
        return len(self.messages)
    
    def add(self, msg):
        """Add new error message to current path."""
        if self.frozen:
            return
        path = [str(p) for p in self.path]
        self.messages.append('[/%s] %s' % ('/'.join(path), msg))

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

"""
class Callable:
    def __init__(self, call):
        self.__call__ = call
"""

def factory(meta='root'):
    """Factory method, return validator instance."""
    v = Validator()
    return v.get_validator(meta)

class Validator(object):

    name = 'validator'

    """
    def factory(meta='root'): # pylint: disable-msg=E0213
        v = Validator()
        return v.get_validator(meta)
    factory = Callable(factory)
    """

    def __init__(self, parent=None):
        self.valid = []
        if parent is None:
            self.errors = Errors()
            self.validators = {}
            
            # register default validators
            register = [RootValidator, ListValidator, DictValidator, TextValidator, AnyValidator, 
                        NumberValidator, BooleanValidator, DecimalValidator, UrlValidator, 
                        ChoiceValidator]
            for v in register:
                self.register(v)
        else:
            self.errors = parent.errors
            self.validators = parent.validators

    def register(self, validator):
        if not hasattr(validator, 'name'):
            raise Exception('Validator %s is missing class-attribute name' % validator.__class__.__name__)
        self.validators[validator.name] = validator

    def get_validator(self, meta):
        if not self.validators.get(meta):
            raise Exception('Asked unknown validator \'%s\'' % meta)
        #print 'returning %s' % meta
        return self.validators[meta](self)

    def accept(self, meta, **kwargs):
        raise Exception('Validator %s should override accept method' % self.__class__.__name__)
    
    def validateable(self, data):
        """Return true if validator can be used to validate given data, False otherwise."""
        raise Exception('Validator %s should override validateable method' % self.__class__.__name__)
        
    def validate(self, data):
        """Validate given data and log errors, return True if passed and False if not."""
        raise Exception('Validator %s should override validate method' % self.__class__.__name__)
        
    def validate_item(self, item, rules):
        """
            Helper method. Validate item against list of rules (validators).
            Return True if item passed some rule. False if none of the rules pass item.
        """
        for rule in rules:
            #print 'validating %s' % rule.name
            if rule.validateable(item):
                if rule.validate(item):
                    return True
        return False

    def __str__(self):
        return '<%s>' % self.name
        
class RootValidator(Validator):
    name = 'root'

    def accept(self, meta, **kwargs):
        v = self.get_validator(meta)
        self.valid.append(v)
        return v
    
    def validate(self, data):
        for v in self.valid:
            if v.validateable(data):
                if v.validate(data):
                    return True
        acceptable = [v.name for v in self.valid]
        self.errors.add('incorrect format, should be %s' % ', '.join(acceptable))
        return False


# borked                
class ChoiceValidator(Validator):
    name = 'choice'

    def accept(self, meta, **kwargs):
        v = self.get_validator(kwargs['value'])
        self.valid.append(v)
        return v

    def validateable(self, data):
        raise Exception('borked')

    def validate(self, data):
        if not self.validate_item(data, self.valid):
            l = [r.name for r in self.valid]
            self.errors.add('must be one of values %s' % (', '.join(l)))
        return True

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
        return True
    
    def validate(self, data):
        return self.valid == data

class NumberValidator(Validator):
    name = 'number'

    def accept(self, meta, **kwargs):
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

    def accept(self, meta, **kwargs):
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

    def accept(self, meta, **kwargs):
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
    
    def accept(self, meta, **kwargs):
        pass

    def validateable(self, data):
        return isinstance(data, basestring)

    def validate(self, data):
        valid = isinstance(data, basestring)
        if not valid:
            self.errors.add('value %s is not valid text' % data)
        return valid

class UrlValidator(Validator):
    name = 'url'
    
    def accept(self, meta, **kwargs):
        pass
        
    def validateable(self, data):
        return isinstance(data, basestring)

    def validate(self, data):
        regexp = '(ftp|http|https):\/\/(\w+:{0,1}\w*@)?(\S+)(:[0-9]+)?(\/|\/([\w#!:.?+=&%@!\-\/]))?'
        if not isinstance(data, basestring):
            self.errors.add('expecting text')
            return False
        valid = re.match(regexp, data) != None
        if not valid:
            self.errors.add('value %s is not valid url' % data)
        return valid
        
class ListValidator(Validator):
    name = 'list'

    def accept(self, meta, **kwargs):
        v = self.get_validator(meta)
#        v.accept(meta, **kwargs)
        self.valid.append(v)
        return v

    def validateable(self, data):
        return isinstance(data, list)

    def validate(self, data):
        if not isinstance(data, list):
            self.errors.add('value should be a list')
            return False
        self.errors.path_add_level()
        ec = self.errors.count()
        for item in data:
            self.errors.path_update_value(data.index(item))
            if not self.validate_item(item, self.valid):
                l = [r.name for r in self.valid]
                self.errors.add('is not valid %s' % (', '.join(l)))
        self.errors.path_remove_level()
        return ec == self.errors.count()

class DictValidator(Validator):
    name = 'dict'

    def __init__(self, parent=None):
        self.reject = []
        self.any_key = []
        self.required_keys = []
        Validator.__init__(self, parent)
        # TODO: not dictionary?
        self.valid = {}

    def accept(self, meta, **kwargs):
        """Accepts key with meta type"""
        if not 'key' in kwargs:
            raise Exception('%s.accept() must specify key' % self.name)

        key = kwargs['key']
        v = self.get_validator(meta)
        self.valid.setdefault(key, []).append(v)
        # complain from old format
        if 'require' in kwargs:
            print 'TODO: REQUIRE USED'
        if kwargs.get('required', False):
            self.require_key(key)
        return v

    def reject_key(self, key):
        """Rejects key"""
        self.reject.append(key)

    def reject_keys(self, keys):
        """Reject list of keys"""
        self.reject.extend(keys)

    def require_key(self, key):
        """Flag key as mandatory"""
        if not key in self.required_keys:
            self.required_keys.append(key)

    def accept_any_key(self, meta, **kwargs):
        """Accepts any key with this given type."""
        v = self.get_validator(meta)
        #v.accept(meta, **kwargs)
        self.any_key.append(v)
        return v

    def validateable(self, data):
        return isinstance(data, dict)
    
    def validate(self, data):
        if not isinstance(data, dict):
            self.errors.add('value should be a dictionary / map')
            return False
        
        ec = self.errors.count()
        self.errors.path_add_level()
        for key, value in data.iteritems():
            self.errors.path_update_value(key)
            if not key in self.valid and not self.any_key:
                self.errors.add('key \'%s\' is not recognized' % key)
                continue
            if key in self.reject:
                self.errors.add('key \'%s\' is forbidden here' % key)
                continue
            # rules contain rules specified for this key AND
            # rules specified for any key
            rules = self.valid.get(key, [])
            rules.extend(self.any_key)
            if not self.validate_item(value, rules):
                l = [r.name for r in rules]
                self.errors.add('key \'%s\' is not valid %s' % (value, ', '.join(l)))
        for required in self.required_keys:
            if not required in data:
                self.errors.add('key \'%s\' required' % required)
        self.errors.path_remove_level()
        return ec == self.errors.count()

if __name__=='__main__':
    
    try:

        container = factory('list')
        entry = container.accept('dict')
        entry.accept('url', key='url', required=True)
        entry.accept('text', key='title', required=True)
        entry.accept_any_key('text')
        entry.accept_any_key('number')

    except Exception, e:
        print e
    finally:
        pass
        #s = raw_input('--> ')