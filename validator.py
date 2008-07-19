import os
import sys
import string
import re

# TODO:
# - patterns validator
# - path validator (with existing check)
# - url validator

class Validator:

    errors = []
    path = []

    def error(self, msg):
        path = [str(p) for p in self.path]
        self.errors.append('[/%s] %s' % (string.join(path, '/'), msg))

    def path_add_level(self, value='?'):
        """Adds one level into error message path list"""
        self.path_level = len(self.path)
        self.path.append(value)

    def path_remove_level(self):
        """Removes level from path by depth number"""
        del(self.path[self.path_level])
        self.path_level = None

    def path_update_value(self, value):
        if not hasattr(self, 'path_level'):
            raise Exception('no path level')
        self.path[self.path_level] = value

    def get_validator(self, meta):
        """Return validator instance for meta-class"""
        if meta == list:
            return ListValidator()
        elif meta == dict:
            return DictValidator()
        else:
            mv = MetaValidator()
            mv.accept(meta)
            return mv

    def try_validate(self, data):
        """Try to validate data without failure on wrong datatype (internal)."""
        if not isinstance(data, self.meta_type()):
            return
        return self.validate(data)

class MetaValidator(Validator):
    def __init__(self):
        self.valid = None

    def accept(self, meta):
        self.valid = meta

    def validate(self, data):
        return isinstance(data, self.valid)

    def meta_type(self):
        """Return metaclass this validator expects"""
        if self.valid is None:
            raise Exception('empty metavalidator')
        return self.valid

class ListValidator(Validator):

    def __init__(self):
        self.valid = []

    def accept(self, meta):
        v = self.get_validator(meta)
        self.valid.append(v)
        return v

    def validate(self, data):
        if not isinstance(data, list):
            self.error('data is not a list')
            return
        passed = True
        self.path_add_level()
        for item in data:
            self.path_update_value(data.index(item))
            # test if matches to any given rules
            item_passed = False
            for rule in self.valid:
                if rule.try_validate(item):
                    item_passed = True
            if not item_passed:
                l = [r.meta_type().__name__ for r in self.valid]
                self.error("is not %s" % (string.join(l, ', ')))
                passed = False
        self.path_remove_level()
        return passed

    def meta_type(self):
        """Return metaclass this validator expects"""
        return list

class DictValidator(Validator):

    def __init__(self):
        self.valid = {}
        self.any_key = []

    def accept(self, key, meta):
        v = self.get_validator(meta)
        self.valid.setdefault(key, []).append(v)
        return v

    def accept_any_key(self, meta):
        v = self.get_validator(meta)
        self.any_key.append(v)
        return v

    def validate(self, data):
        if not isinstance(data, dict):
            self.error('data is not a dict')
            return
        passed = True
        self.path_add_level()
        for key, value in data.iteritems():
            self.path_update_value(key)
            if not self.valid.has_key(key) and not self.any_key:
                self.error("key '%s' is undefined" % key)
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
                l = [r.meta_type().__name__ for r in rules]
                self.error("'%s' is not %s" % (value, string.join(l, ', ')))
                passed = False
        self.path_remove_level()
        return passed

    def meta_type(self):
        """Return metaclass this validator expects"""
        return dict

if __name__=='__main__':
    l = ['aaa','bbb','ccc', 123, {'xxax':'yyyy', 'yyy': 12}]

    lv = ListValidator()
    lv.accept(str)
    lv.accept(int)
    dv = lv.accept(dict)
    dv.accept('xxx', str)
    dv.accept('yyy', str)
    dv.accept('yyy', float)
    dv.accept('yyy', list)
    
    lv.validate(l)

    print "errors:"
    for err in lv.errors:
        print err
    
            



        
