
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
        else:
            raise Exception('unknown type')

    def try_validate(self, data):
        """Try to validate, should not fail on wrong datatype."""
        try:
            return self.validate(data)
        except Exception, e:
            pass

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
            raise Exception('data is not a list')
        passed = True
        self.errors.path_add_level()
        for item in data:
            self.errors.path_update_value(data.index(item))
            # test if matches to any given rules
            item_passed = False
            for rule in self.valid:
                if rule.try_validate(item):
                    item_passed = True
            if not item_passed:
                l = [r.meta_type() for r in self.valid]
                self.errors.add("is not valid %s" % (', '.join(l)))
                passed = False
        self.errors.path_remove_level()
        return passed

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

    def accept(self, key, meta):
        v = self.get_validator(meta)
        self.valid.setdefault(key, []).append(v)
        return v

    def require(self, key):
        if not key in self.required_keys:
            self.required_keys.append(key)

    def accept_any_key(self, meta):
        v = self.get_validator(meta)
        self.any_key.append(v)
        return v

    def validate(self, data):
        if not isinstance(data, dict):
            raise Exception('data is not a dict')
        passed = True
        self.errors.path_add_level()
        for key, value in data.iteritems():
            self.errors.path_update_value(key)
            if not self.valid.has_key(key) and not self.any_key:
                self.errors.add("key '%s' is undefined" % key)
                continue
            # test if matches to any given rules
            item_passed = False
            # rules contain rules specified for this key AND
            # rules specified for any key
            rules = self.valid.get(key, [])
            rules.extend(self.any_key)
            for rule in rules:
                if rule.try_validate(value):
                    item_passed = True
            if not item_passed:
                l = [r.meta_type() for r in rules]
                self.errors.add("key '%s' is not valid %s" % (value, ', '.join(l)))
                passed = False
        for required in self.required_keys:
            if not data.has_key(required):
                self.errors.add("key '%s' must be defined" % required)
                passed = False
        self.errors.path_remove_level()
        return passed

    def meta_type(self):
        return 'dict'

if __name__=='__main__':
    l = ['aaa','bbb','ccc', 123, {'xxax':'yyyy', 'yyy': ['a','b','c']}]

    lv = ListValidator()
    lv.accept(str)
    lv.accept(int)
    dv = lv.accept(dict)
    dv.accept('xxx', str)
    dv.accept('yyy', str)
    dv.accept('yyy', float)
    dv.require('foo')
    ll = dv.accept('yyy', list)
    ll.accept('a')
    ll.accept('b')
    
    lv.validate(l)

    print "errors:"
    for err in lv.errors.messages:
        print err
