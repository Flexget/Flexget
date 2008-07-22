
# TODO:
# - patterns validator
# - path validator (with existing check)
# - url validator

class TypeException(Exception):
    pass

class Errors:

    def __init__(self):
        self.messages = []
        self.path = []
        self.path_level = None

    def add(self, msg):
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

class Validator:

    def get_validator(self, t):
        """Return validator instance"""
        if not hasattr(self, 'errors'):
            self.errors = None
        # choose
        if t == list:
            return ListValidator(self.errors)
        elif t == dict:
            return DictValidator(self.errors)
        elif t == int or t == float or t == bool or t == str:
            mv = MetaValidator(self.errors)
            mv.accept(t)
            return mv
        elif isinstance(t, str):
            sv = ValueValidator(self.errors)
            sv.accept(t)
            return sv
        elif isinstance(t, list):
            vlv = ValueListValidator(self.errors)
            for v in t:
                vlv.accept(v)
            return vlv
        else:
            raise Exception('unknown type')

    def validate_item(self, item, rules):
        """Helper method. Validate list of items against list of rules (validators).
        Return True if item matches to any of the rules.
        Raises TypeException if it could not be even tried."""
        failed = True
        for rule in rules:
            try:
                if rule.validate(item):
                    return True
                failed = False
            except TypeException, e:
                pass
        if failed:
            raise TypeException()

class ValueValidator(Validator):

    def __init__(self, errors=None):
        self.valid = None
        if errors is None:
            errors = Errors()
        self.errors = errors

    def accept(self, value):
        self.valid = value

    def validate(self, data):
        return data == self.valid

    def meta_type(self):
        return '%s' % self.valid


class ValueListValidator(Validator):

    def __init__(self, errors=None):
        self.valid = []
        if errors is None:
            errors = Errors()
        self.errors = errors

    def accept(self, value):
        v = self.get_validator(value)
        self.valid.append(v)
        return v

    def validate(self, data):
        try:
            if not self.validate_item(data, self.valid):
                l = [r.meta_type() for r in self.valid]
                self.errors.add("must be one of values %s" % (', '.join(l)))
        except TypeException, e:
            pass
        return True
        

class MetaValidator(Validator):
    
    def __init__(self, errors=None):
        self.valid = None
        if errors is None:
            errors = Errors()
        self.errors = errors

    def accept(self, meta):
        self.valid = meta

    def validate(self, data):
        return isinstance(data, self.valid)

    def meta_type(self):
        if self.valid is None:
            raise Exception('empty metavalidator')
        return self.valid.__name__

class ListValidator(Validator):

    def __init__(self, errors=None):
        self.valid = []
        if errors is None:
            errors = Errors()
        self.errors = errors

    def accept(self, meta):
        v = self.get_validator(meta)
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
                    l = [r.meta_type() for r in self.valid]
                    self.errors.add("is not valid %s" % (', '.join(l)))
            except TypeException, e:
                pass
        self.errors.path_remove_level()
        
        # validation succeeded, errors are logged so it's considered clean!
        return True

    def meta_type(self):
        return 'list'

class DictValidator(Validator):

    def __init__(self, errors=None):
        self.valid = {}
        self.any_key = []
        self.required_keys = []
        if errors is None:
            errors = Errors()
        self.errors = errors

    def accept(self, key, meta, **kwargs):
        """Accepts key with meta type"""
        v = self.get_validator(meta)
        self.valid.setdefault(key, []).append(v)
        if kwargs.get('require', False):
            self.require(key)
        return v

    def require(self, key):
        """Flag key as mandatory"""
        if not key in self.required_keys:
            self.required_keys.append(key)

    def accept_any_key(self, meta):
        """Accepts all keys with given meta type, regardless of name"""
        v = self.get_validator(meta)
        self.any_key.append(v)
        return v

    def validate(self, data):
        if not isinstance(data, dict):
            raise TypeException('validate data is not a dict')
        self.errors.path_add_level()
        for key, value in data.iteritems():
            self.errors.path_update_value(key)
            if not self.valid.has_key(key) and not self.any_key:
                self.errors.add("key is unknown")
                continue
            # rules contain rules specified for this key AND
            # rules specified for any key
            rules = self.valid.get(key, [])
            rules.extend(self.any_key)
            try:
                if not self.validate_item(value, rules):
                    l = [r.meta_type() for r in rules]
                    self.errors.add("key '%s' is not valid %s" % (value, ', '.join(l)))
            except TypeException, e:
                pass
        for required in self.required_keys:
            if not data.has_key(required):
                self.errors.add("key '%s' must be present" % required)
        self.errors.path_remove_level()
        
        # validation succeeded, errors are logged so it's considered clean!
        return True

    def meta_type(self):
        return 'dict'

if __name__=='__main__':
    l = ['aaa','bbb','ccc', 123, {'xxax':'yyyy', 'zzz': 'c'}]

    lv = ListValidator()
    lv.accept(str)
    lv.accept(int)
    dv = lv.accept(dict)
    dv.accept('xxx', str)
    dv.accept('yyz', str, require=True)
    dv.accept('yyy', float)
    dv.require('foo')
    dv.accept('zzz', ['a','b'])

    lv.validate(l)

    print "errors:"
    for err in lv.errors.messages:
        print err
