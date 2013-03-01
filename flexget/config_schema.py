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


def resolve_local(uri):
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


format_checker = jsonschema.FormatChecker(('regex', 'email'))


@format_checker.checks('quality')
def is_quality(instance):
    try:
        qualities.get(instance)
        return True
    except ValueError:
        return False


@format_checker.checks('quality_requirements')
def is_quality_requirements(instance):
    try:
        qualities.Requirements(instance)
        return True
    except ValueError:
        return False


@format_checker.checks('file')
def is_file(instance):
    if not os.path.isfile(os.path.expanduser(instance)):
        return False
    return True


#TODO: jsonschema has a format checker for uri if rfc3987 is installed, perhaps we should use that
@format_checker.checks('url')
def is_url(instance):
    regexp = ('(' + '|'.join(['ftp', 'http', 'https', 'file', 'udp']) +
              '):\/\/(\w+:{0,1}\w*@)?(\S+)(:[0-9]+)?(\/|\/([\w#!:.?+=&%@!\-\/]))?')
    return re.match(regexp, instance) is not None


class SchemaValidator(jsonschema.Draft4Validator):
    """
    Validator for our schemas.
    Sets up local ref resolving and our custom format checkers.
    """
    def __init__(self, schema):
        resolver = jsonschema.RefResolver.from_schema(schema)
        resolver.handlers[''] = resolve_local
        super(SchemaValidator, self).__init__(schema, resolver=resolver, format_checker=format_checker)


def one_or_more(schema):
    """
    Helper function to construct a schema that accepts the given `schema` or an array containing the given schema.
    """

    return {'anyOf': [
        schema,
        {'type': 'array', 'items': schema}
    ]}
