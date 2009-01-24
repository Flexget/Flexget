import re

# TODO: get rid of TypeException, bad exception! Or atleast improve it's usage!
# TODO: "validation succeeded, errors are logged so it's considered clean!"
# TODO: rename all validator.valid -> validator.accepts / accepted / accept

class TypeException(Exception):
    pass

class Errors:

    def __init__(self):
        self.messages = []
        self.path = []
        self.path_level = None

    def add(self, msg):
        path = [str(p) for p in self.path]
        self.messages.append('[%s] %s' % ('/'.join(path), msg))

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

class Callable:
    def __init__(self, call):
        self.__call__ = call

class Validator(object):

    def factory(meta='root'):
        v = Validator()
        return v.get_validator(meta)
    factory = Callable(factory)

    def __init__(self, parent=None):
        self.valid = []
        if parent is None:
            self.errors = Errors()
            self.validators = {}
            
            # register default handlers
            self.register(RootValidator)
            self.register(ListValidator)
            self.register(DictValidator) 
            self.register(TextValidator)
            self.register(NumberValidator)
            self.register(UrlValidator)
            self.register(ChoiceValidator)
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
        print 'returning %s' % meta
        return self.validators[meta](self)

    def accept(self, **kwargs):
        # TODO: should it?
        raise Exception('Validator %s should override accept method?' % self.__class__.__name__)
        
    def validate_item(self, item, rules):
        """
            Helper method. Validate item against list of rules (validators).
            Return True if item passed some rule. False if none of the rules pass item.
            Raises TypeException if it could not be even tried (wrong type).
        """
        failed = True
        for rule in rules:
            try:
                print 'validating %s' % rule.name
                if rule.validate(item):
                    return True
                failed = False
            except TypeException, e:
                pass
        if failed:
            raise TypeException()

    def __str__(self):
        return '<%s>' % self.name

    # TODO: remove
    def __repr__(self):
        return '<%s>' % self.name
        
        
class RootValidator(Validator):
    name = 'root'

    """
    def __init__(self, parent=None):
        Validator.__init__(self, parent)
        self.valid.append(self.get_validator('dict'))
        self.valid.append(self.get_validator('list'))
    """
    
    def accept(self, meta, **kwargs):
        v = self.get_validator(meta)
        self.valid.append(v)
        return v
    
    def validate(self, data):
        for v in self.valid:
            try:
                v.validate(data)
                return True
            except TypeException, e:
                pass
        self.errors.add('incorrect format')
        return False


# borked                
class ChoiceValidator(Validator):
    name = 'choice'

    def accept(self, value):
        v = self.get_validator(value)
        self.valid.append(v)
        return v

    def validate(self, data):
        try:
            if not self.validate_item(data, self.valid):
                l = [r.name for r in self.valid]
                self.errors.add('must be one of values %s' % (', '.join(l)))
        except TypeException, e:
            pass
        return True

class EqualsValidator(Validator):
    name = 'equals'

    def accept(self, value, **kwargs):
        self.valid = value

    def validate(self, data):
        return self.valid == data

class NumberValidator(Validator):
    name = 'number'

    def accept(self, meta, **kwargs):
        pass

    def validate(self, data):
        return isinstance(data, int) or isinstance(data, float)


class TextValidator(Validator):
    name = 'text'
    
    def accept(self, meta, **kwargs):
        pass

    def validate(self, data):
        return isinstance(data, basestring)

class UrlValidator(Validator):
    name = 'url'
    
    def accept(self, meta, **kwargs):
        pass
        
    def validate(self, data):
        regexp = '(ftp|http|https):\/\/(\w+:{0,1}\w*@)?(\S+)(:[0-9]+)?(\/|\/([\w#!:.?+=&%@!\-\/]))?'
        return re.match(regexp, data) != None
        
        
class ListValidator(Validator):
    name = 'list'

    def accept(self, meta, **kwargs):
        v = self.get_validator(meta)
        v.accept(meta, kwargs)
        self.valid.append(v)
        return v

    def validate(self, data):
        if not isinstance(data, list):
            raise TypeException('validate data is not a list')
        self.errors.path_add_level()
        for item in data:
            self.errors.path_update_value(data.index(item))
            try:
                if not self.validate_item(item, self.valid):
                    l = [r.name for r in self.valid]
                    self.errors.add('is not valid %s' % (', '.join(l)))
            except TypeException, e:
                pass
        self.errors.path_remove_level()
        
        # validation succeeded, errors are logged so it's considered clean!
        return True

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
        if not kwargs.has_key('key'):
            # not sure if this is good idea, quite implicit
            return self.accept_any_key(meta)
        else:
            key = kwargs['key']
            v = self.get_validator(meta)
            self.valid.setdefault(key, []).append(v)
            if kwargs.get('require', False):
                self.require(key)
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
        v.accept(meta, kwargs)
        self.any_key.append(v)
        return v

    def validate(self, data):
        if not isinstance(data, dict):
            raise TypeException('validate data is not a dict')
        self.errors.path_add_level()
        for key, value in data.iteritems():
            self.errors.path_update_value(key)
            if not self.valid.has_key(key) and not self.any_key:
                self.errors.add('unknown key')
                continue
            if key in self.reject:
                self.errors.add('key \'%s\' is forbidden here' % key)
            # rules contain rules specified for this key AND
            # rules specified for any key
            rules = self.valid.get(key, [])
            rules.extend(self.any_key)
            try:
                if not self.validate_item(value, rules):
                    l = [r.name for r in rules]
                    self.errors.add('key \'%s\' is not valid %s' % (value, ', '.join(l)))
            except TypeException, e:
                pass
        for required in self.required_keys:
            if not data.has_key(required):
                self.errors.add('key \'%s\' required' % required)
        self.errors.path_remove_level()
        
        # validation succeeded, errors are logged so it's considered clean!
        return True

if __name__=='__main__':
    
    try:
    
        data={'foo':'value', 'key5':5, 'url':'http://test.com'}
        
        root = Validator.factory()
        d = root.accept('dict')
        d.accept('url', key='url')

        #d.accept('text', key='key1')
        #d.accept('text', require=True)
        #d.accept('number', key='key2')
        #inner = root.accept('key4', 'dict')
        
        #choice = d.accept('key5', 'choice', require=True)
        #choice.accept('equals', 1)

        root.validate(data)

        print root.valid

        #n = Validator.factory('number')
        #n.accept()

        print "errors:"
        for err in root.errors.messages:
            print err

    except Exception, e:
        print e
    finally:
        s = raw_input('--> ')
