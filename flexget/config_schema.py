from __future__ import unicode_literals, division, absolute_import
import os
import re
import urlparse
from collections import defaultdict

import jsonschema

from flexget.utils import qualities, template

schema_paths = {}


def register_schema(path, schema):
    """
    Register `schema` to be available at `path` for $refs

    :param path: Path to make schema available
    :param schema: The schema, or function which returns the schema
    """
    schema_paths[path] = schema


def resolve_ref(uri):
    """
    Finds and returns a schema pointed to by `uri` that has been registered in the register_schema function.
    """
    parsed = urlparse.urlparse(uri)
    if parsed.path in schema_paths:
        schema = schema_paths[parsed.path]
        if callable(schema):
            return schema(**dict(urlparse.parse_qsl(parsed.query)))
        return schema
    raise jsonschema.RefResolutionError("%s could not be resolved" % uri)


class RefResolver(jsonschema.RefResolver):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('handlers', {'': resolve_ref})
        super(RefResolver, self).__init__(*args, **kwargs)


format_checker = jsonschema.FormatChecker(('email',))
format_checker.checks('quality', raises=ValueError)(qualities.get)
format_checker.checks('quality_requirements', raises=ValueError)(qualities.Requirements)

@format_checker.checks('regex', raises=ValueError)
def is_regex(instance):
    try:
        return re.compile(instance)
    except re.error as e:
        raise ValueError('Error parsing regex: %s' % e)

@format_checker.checks('file', raises=ValueError)
def is_file(instance):
    if os.path.isfile(os.path.expanduser(instance)):
        return True
    raise ValueError('`%s` does not exist' % instance)

@format_checker.checks('path', raises=ValueError)
def is_path(instance):
    # Only validate the part of the path before the first identifier to be replaced
    pat = re.compile(r'{[{%].*[}%]}')
    result = pat.search(instance)
    if result:
        instance = os.path.dirname(instance[0:result.start()])
    if os.path.isdir(os.path.expanduser(instance)):
        return True
    raise ValueError('`%s` does not exist' % instance)


#TODO: jsonschema has a format checker for uri if rfc3987 is installed, perhaps we should use that
@format_checker.checks('url')
def is_url(instance):
    regexp = ('(' + '|'.join(['ftp', 'http', 'https', 'file', 'udp']) +
              '):\/\/(\w+:{0,1}\w*@)?(\S+)(:[0-9]+)?(\/|\/([\w#!:.?+=&%@!\-\/]))?')
    return re.match(regexp, instance)

@format_checker.checks('interval', raises=ValueError)
def is_interval(instance):
    regexp = r'^\d+ (second|minute|hour|day|week)s?$'
    if not re.match(regexp, instance):
        raise ValueError("should be in format 'x (seconds|minutes|hours|days|weeks)'")
    return True


class ValidationError(jsonschema.ValidationError):
    """
     Overrides error messages from jsonschema with custom ones for FlexGet

    """

    @property
    def error_with_path(self):
        return "[/%s] %s" % ('/'.join(map(unicode, self.path)), self.message)

    @property
    def message(self):
        custom_error = self.schema.get('error_%s' % self.validator, self.schema.get('error'))
        if custom_error:
            return template.render(custom_error, self.__dict__)
        elif hasattr(self, 'message_%s' % self.validator):
            return getattr(self, 'message_%s' % self.validator)()
        return self._message

    @message.setter
    def message(self, value):
        self._message = value

    def message_type(self):
        if isinstance(self.validator_value, basestring):
            valid_types = [self.validator_value]
        else:
            valid_types = list(self.validator_value)
        # Replace some types with more pythony ones
        replace = {'object': 'dict', 'array': 'list'}
        valid_types = [replace.get(t, t) for t in valid_types]
        # Make valid_types into an english list, with commas and 'or'
        valid_types = ', '.join(valid_types[:-2] + ['']) + ' or '.join(valid_types[-2:])
        if isinstance(self.instance, dict):
            return 'Got a dict, expected: %s' % valid_types
        if isinstance(self.instance, list):
            return 'Got a list, expected: %s' % valid_types
        return 'Got `%s`, expected: %s' % (self.instance, valid_types)

    def message_format(self):
        if self.cause:
            return unicode(self.cause)
        return self._message

    def message_enum(self):
        return 'Must be one of the following: %s' % ', '.join(map(unicode, self.validator_value))

    def message_additionalProperties(self):
        if self.validator_value is False:
            extras = set(jsonschema._find_additional_properties(self.instance, self.schema))
            if len(extras) == 1:
                return 'The key `%s` is not valid here.' % extras.pop()
            else:
                return 'The keys %s are not valid here.' % ', '.join('`%s`' % e for e in extras)
        return self._message


class SchemaValidator(jsonschema.Draft4Validator):
    """
    Validator for our schemas.
    Sets up local ref resolving and our custom format checkers.
    """
    def __init__(self, schema):
        resolver = RefResolver.from_schema(schema)
        super(SchemaValidator, self).__init__(schema, resolver=resolver, format_checker=format_checker)
        self.set_defaults = False

    def process_config(self, config):
        """
        Validates the instance, and sets defaults within it.

        :returns: A list with :class:`ValidationError`s if any

        """
        self.set_defaults = True
        try:
            return list(self.iter_errors(config))
        finally:
            self.set_defaults = False

    def iter_errors(self, instance, _schema=None):
        for e in super(SchemaValidator, self).iter_errors(instance, _schema=_schema):
            yield ValidationError.create_from(e)

    def validate_anyOf(self, *args, **kwargs):
        for error in super(SchemaValidator, self).validate_anyOf(*args, **kwargs):
            # Split the suberrors up by which subschema they are from
            subschema_errors = defaultdict(list)
            for sube in error.context:
                subschema_errors[sube.schema_path[0]].append(sube)
            # Find the subschemas that did not have a 'type' error validating the instance at this path
            no_type_errors = dict(subschema_errors)
            valid_types = set()
            for i, errors in subschema_errors.iteritems():
                for e in errors:
                    if e.validator == 'type' and not e.path:
                        # Remove from the no_type_errors dict
                        no_type_errors.pop(i, None)
                        # Add the valid types to the list of all valid types
                        if self.is_type(e.validator_value, 'string'):
                            valid_types.add(e.validator_value)
                        else:
                            valid_types.update(e.validator_value)
            if not no_type_errors:
                # If all of the branches had a 'type' error, create our own virtual type error with all possible types
                for e in self.descend(error.instance, {'type': valid_types}):
                    yield e
            elif len(no_type_errors) == 1:
                # If one of the possible schemas did not have a 'type' error, assume that is the intended one and issue
                # all errors from that subschema
                for e in no_type_errors.values()[0]:
                    e.schema_path.extendleft(reversed(error.schema_path))
                    e.path.extendleft(reversed(error.path))
                    yield e
            else:
                yield error

    def validate_properties(self, properties, instance, schema):
        if not self.is_type(instance, 'object'):
            return
        if self.set_defaults:
            for key, subschema in properties.iteritems():
                if 'default' in subschema:
                    instance.setdefault(key, subschema['default'])
        for error in super(SchemaValidator, self).validate_properties(properties, instance, schema):
            yield error


def one_or_more(schema):
    """
    Helper function to construct a schema that validates items matching `schema` or an array
    containing items matching `schema`.

    """

    return {
        "anyOf": [
            schema,
            {"type": "array", "items": schema, "minItems": 1}
        ]
    }
