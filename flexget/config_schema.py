from __future__ import unicode_literals, division, absolute_import
import os
import re
import urlparse

import jsonschema

from flexget.utils import qualities

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

@format_checker.checks('interval')
def is_interval(instance):
    regexp = r'^\d+ (second|minute|hour|day|week)s?$'
    return re.match(regexp, instance)


class SchemaValidator(jsonschema.Draft4Validator):
    """
    Validator for our schemas.
    Sets up local ref resolving and our custom format checkers.
    """
    def __init__(self, schema):
        resolver = RefResolver.from_schema(schema)
        super(SchemaValidator, self).__init__(schema, resolver=resolver, format_checker=format_checker)


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
