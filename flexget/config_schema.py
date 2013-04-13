from __future__ import unicode_literals, division, absolute_import
import os
import re
import urlparse

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


format_checker = jsonschema.FormatChecker(('regex', 'email'))
format_checker.checks('quality', raises=ValueError)(qualities.get)
format_checker.checks('quality_requirements', raises=ValueError)(qualities.Requirements)


@format_checker.checks('file')
def is_file(instance):
    return os.path.isfile(os.path.expanduser(instance))

@format_checker.checks('path')
def is_path(instance):
    # If string replacement is allowed, only validate the part of the
    # path before the first identifier to be replaced
    pat = re.compile(r'{[{%].*[}%]}')
    result = pat.search(instance)
    if result:
        path = os.path.dirname(instance[0:result.start()])
    return os.path.isdir(os.path.expanduser(instance))


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
        raise ValueError("should be in format 'x (seconds|minutes|hours|days|weeks)")
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
        return self._message.replace("'object'", "'dict'")

    def message_format(self):
        if self.cause:
            return unicode(self.cause)
        return self._message


class SchemaValidator(jsonschema.Draft4Validator):
    """
    Validator for our schemas.
    Sets up local ref resolving and our custom format checkers.
    """
    def __init__(self, schema):
        resolver = RefResolver.from_schema(schema)
        super(SchemaValidator, self).__init__(schema, resolver=resolver, format_checker=format_checker)

    def iter_errors(self, instance, _schema=None):
        for e in super(SchemaValidator, self).iter_errors(instance, _schema=_schema):
            yield ValidationError.create_from(e)

    def validate_anyOf(self, *args, **kwargs):
        for error in super(SchemaValidator, self).validate_anyOf(*args, **kwargs):
            subschema_errors = {}
            for sube in error.context:
                subschema_errors.setdefault(sube.schema_path[0], []).append(sube)
            no_type_errors = [i for i, errors in subschema_errors.iteritems()
                              if not any(e.schema_path[1] == 'type' for e in errors)]
            if len(no_type_errors) == 1:
                # If one of the possible schemas did not have a 'type' error, assume that is the intended one and issue
                # all errors from that subschema
                for e in subschema_errors[no_type_errors[0]]:
                    e.schema_path.extendleft(reversed(error.schema_path))
                    e.path.extendleft(reversed(error.path))
                    yield e
            else:
                yield error



def one_or_more(schema):
    """
    Helper function to construct a schema that validates items matching `schema` or an array
    containing items matching `schema`.

    Limitation: `schema` must not be a schema that validates arrays already
    """

    assert 'array' not in schema.get('type', []), 'Cannot use array schemas with one_or_more'
    new_schema = schema.copy()
    if 'type' in schema:
        if isinstance(schema['type'], basestring):
            new_schema['type'] = [schema['type'], 'array']
        else:
            new_schema['type'] = schema['type'] + ['array']
    new_schema['items'] = schema
    new_schema['minItems'] = 1

    return new_schema
