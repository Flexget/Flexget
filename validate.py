import types
import datetime
import re
import string

class Validate:

    """
        Implements kwalify style validator for any python standard datatype structure.
        Most useful when working with parsing user editable Yaml files.

        Does not (yet) implement kwalify syntax 100% and since this does not
        operate when parsing actual file it will never be quite as good.

        See more document about the syntax at:
        http://www.kuwata-lab.com/kwalify/ruby/users-guide.html

        Kudos for kuwata-labs for making good documentation with lots of testing material!

        License: MIT
    """

    def __init__(self, data, schema):
        self.data = data
        self.schema = schema
        self.errors = []
        self.path = []

    def validate(self):
        if isinstance(self.data, list):
            self.validate_list(self.data, self.schema)
        elif isinstance(self.data, dict):
            self.validate_map(self.data, self.schema)

    def error(self, msg):
        path = [] # TODO: use listcomp?
        for p in self.path:
            path.append(str(p))
        self.errors.append('[/%s] %s' % (string.join(path, '/'), msg))

    def path_add_level(self, value='?'):
        """Adds one level into error message path list, returns level number so
        methods can use that to update value"""
        level = len(self.path)
        self.path.append(value)
        return level

    def path_remove_level(self, level):
        """Removes level from path by depth number"""
        del(self.path[level])

    def validate_list(self, items, schema):
        if not schema['type']=='seq':
            self.error('Sequence has invalid type %s' % schema['type'])
        # TODO: should we use constrains check method here instead of checking manually?
        schema_type = schema['sequence'][0]['type']
        level = self.path_add_level(0)
        if schema_type=='map':
            # sequence of mapping
            item_schema = schema['sequence'][0]
            for item in items:
                self.validate_map(item, item_schema)
                self.path[level] =+ 1
        else:
            # normal sequence
            for item in items:
                if not self.istype(item, schema_type):
                    self.error('seq item %s is not %s' % (item, schema_type))
                self.path[level] =+ 1
        self.path_remove_level(level)

    def validate_map(self, data, schema):
        mapping = schema['mapping']
        level = self.path_add_level()
        for k, v in data.iteritems():
            self.path[level] = k
            if not mapping.has_key(k):
                self.error('key %s is undefined.' % k)
                continue
            # check type constraint
            # TODO: migrate into check_constraints ?
            if not self.istype(v, mapping[k]['type']):
                self.error('value %s is not %s' % (v, mapping[k]['type']))
            # recurse if sequence
            if mapping[k]['type']=='seq':
                self.validate_list(v, mapping[k])
                continue
            # check constraints
            self.check_constraints(v, mapping[k])
        # check for required constraint
        for k, v in mapping.iteritems():
            self.path[level] = k
            if isinstance(v, dict):
                if v.get('required', False):
                    if not data.has_key(k):
                        self.error('key name %s is required.' % k)
        self.path_remove_level(level)

    def check_constraints(self, v, schema):
        """Checks that variable meets constraints defined in schema"""
        # length (applies only to text, str)
        if schema.get('length'):
            l = schema.get('length')
            if l.get('min'):
                if len(v) < l['min']:
                    self.error('%s too short (length %s < min %s)' % (v, len(v), l['min']))
            if l.get('max'):
                if len(v) > l['max']:
                    self.error('%s too long (length %s > max %s)' % (v, len(v), l['max']))
        #  range (applies only to int, float?)
        if schema.get('range'):
            r = schema.get('range')
            if r.get('min'):
                if v < r['min']:
                    self.error('%s too small (< min %s).' % (v, r['min']))
            if r.get('max'):
                if v > r['max']:
                    self.error('%s too big (> max %s).' % (v, r['max']))
        # enum
        if schema.get('enum'):
            if not v in schema['enum']:
                self.error('%s is invalid enum value' % v)
        # pattern
        pattern = schema.get('pattern')
        if pattern:
            # DEBUG !!!!
            if pattern=='/@/':
                pattern='.*'
            # DEBUG !!!!
            if not re.match(pattern, v):
                self.error('%s not matched to pattern %s.' % (v, pattern))
        # unique
        if schema.get('unique'):
            # TODO
            self.error('unique constraint is not supported yet')

    def istype(self, var, schema_type):
        """                                        
            str, int, float
            number (== int or float)
            text (== str or number)
            bool, date, time, timestamp
            seq, map
            scalar (all but seq and map)
            any (means any data)
        """
        # TODO UNSUPPORTED: time, timestamp
        schema_types = {'str': str, 'int': int, 'float': float, 'map': dict, 'seq': list,
                        'date': datetime.date, 'bool': bool}
        if schema_types.has_key(schema_type):
            return isinstance(var, schema_types[schema_type])
        if schema_type=='text':
            return isinstance(var, str) or isinstance(var, int) or isinstance(var, float)
        if schema_type=='scalar':
            if isinstance(var, list) or isinstance(var, dict):
                return False
            else:
                return True
        if schema_type=='any':
            return True
        raise Exception('unknown type %s in schema' % schema_type)

if __name__ == "__main__":
    import yaml
    import os
    import sys
    sf = file(sys.argv[1], 'r')
    schema = yaml.safe_load(sf)
    df = file(sys.argv[2], 'r')
    data = yaml.safe_load(df)
    sf.close()
    df.close()
    print "SCHEMA: %s" % ("-"*52)
    print schema
    print "DATA  : %s" % ("-"*52)
    print data
    print "-"*60
    v = Validate(data, schema)
    v.validate()
    for e in v.errors:
        print e
    if not v.errors:
        print "PASSED"
