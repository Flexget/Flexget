from __future__ import absolute_import, division, unicode_literals

import os
import re
import urlparse
from collections import defaultdict
from datetime import datetime

import jsonschema
from jsonschema.compat import str_types, int_types

from flexget.event import fire_event
from flexget.utils import qualities, template
from flexget.utils.tools import parse_timedelta

schema_paths = {}


# TODO: Rethink how config key and schema registration work
def register_schema(path, schema):
    """
    Register `schema` to be available at `path` for $refs

    :param path: Path to make schema available
    :param schema: The schema, or function which returns the schema
    """
    schema_paths[path] = schema


# Validator that handles root structure of config.
_root_config_schema = None


def register_config_key(key, schema, required=False):
    """ Registers a valid root level key for the config.

    :param string key:
      Name of the root level key being registered.
    :param dict schema:
      Schema for the key.
    :param bool required:
      Specify whether this is a mandatory key.
    """
    _root_config_schema['properties'][key] = schema
    if required:
        _root_config_schema.setdefault('required', []).append(key)
    register_schema('/schema/config/%s' % key, schema)


def get_schema():
    global _root_config_schema
    if _root_config_schema is None:
        _root_config_schema = {'type': 'object', 'properties': {}, 'additionalProperties': False}
        fire_event('config.register')
        # TODO: Is /schema/root this the best place for this?
        register_schema('/schema/config', _root_config_schema)
    return _root_config_schema


def one_or_more(schema):
    """
    Helper function to construct a schema that validates items matching `schema` or an array
    containing items matching `schema`.

    """

    schema.setdefault('title', 'single value')
    return {
        'oneOf': [
            {'title': 'multiple values', 'type': 'array', 'items': schema, 'minItems': 1},
            schema
        ]
    }


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


def process_config(config, schema=None, set_defaults=True):
    """
    Validates the config, and sets defaults within it if `set_defaults` is set.
    If schema is not given, uses the root config schema.

    :returns: A list with :class:`jsonschema.ValidationError`s if any

    """
    if schema is None:
        schema = get_schema()
    resolver = RefResolver.from_schema(schema)
    validator = SchemaValidator(schema, resolver=resolver, format_checker=format_checker)
    if set_defaults:
        validator.VALIDATORS['properties'] = validate_properties_w_defaults
    try:
        errors = list(validator.iter_errors(config))
    finally:
        validator.VALIDATORS['properties'] = jsonschema.Draft4Validator.VALIDATORS['properties']
    # Customize the error messages
    for e in errors:
        set_error_message(e)
        e.json_pointer = '/' + '/'.join(map(unicode, e.path))
    return errors


def parse_time(time_string):
    """Parse a time string from the config into a :class:`datetime.time` object."""
    formats = ['%I:%M %p', '%H:%M', '%H:%M:%S']
    for f in formats:
        try:
            return datetime.strptime(time_string, f).time()
        except ValueError:
            continue
    raise ValueError('invalid time `%s`' % time_string)


def parse_interval(interval_string):
    """Takes an interval string from the config and turns it into a :class:`datetime.timedelta` object."""
    regexp = r'^\d+ (second|minute|hour|day|week)s?$'
    if not re.match(regexp, interval_string):
        raise ValueError("should be in format 'x (seconds|minutes|hours|days|weeks)'")
    return parse_timedelta(interval_string)


def parse_percent(percent_input):
    """Takes a size string from the config and turns it into int(bytes)."""
    percent_input = percent_input.rstrip('%')
    try:
        return float(percent_input)
    except ValueError:
        raise ValueError("should be in format '0-x%'")


def parse_size(size_input):
    """Takes a size string from the config and turns it into int(bytes)."""
    prefixes = [None, 'K', 'M', 'G', 'T', 'P']
    try:
        # Bytes
        return int(size_input)
    except ValueError:
        size_input = size_input.upper().rstrip('IB')
        value, unit = float(size_input[:-1]), size_input[-1:]
        if unit not in prefixes:
            raise ValueError("should be in format '0-x (KiB, MiB, GiB, TiB, PiB)'")
        return int(1024 ** prefixes.index(unit) * value)


## Public API end here, the rest should not be used outside this module


class RefResolver(jsonschema.RefResolver):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('handlers', {'': resolve_ref})
        super(RefResolver, self).__init__(*args, **kwargs)


format_checker = jsonschema.FormatChecker(('email',))


@format_checker.checks('quality', raises=ValueError)
def is_quality(instance):
    if not isinstance(instance, str_types):
        return True
    return qualities.get(instance)


@format_checker.checks('quality_requirements', raises=ValueError)
def is_quality_req(instance):
    if not isinstance(instance, str_types):
        return True
    return qualities.Requirements(instance)



@format_checker.checks('time', raises=ValueError)
def is_time(time_string):
    if not isinstance(time_string, str_types):
        return True
    return parse_time(time_string) is not None


@format_checker.checks('interval', raises=ValueError)
def is_interval(interval_string):
    if not isinstance(interval_string, str_types):
        return True
    return parse_interval(interval_string) is not None


@format_checker.checks('size', raises=ValueError)
def is_size(size_string):
    if not isinstance(size_string, (str_types, int_types)):
        return True
    return parse_size(size_string) is not None


@format_checker.checks('percent', raises=ValueError)
def is_percent(percent_string):
    if not isinstance(percent_string, str_types):
        return True
    return parse_percent(percent_string) is not None


@format_checker.checks('regex', raises=ValueError)
def is_regex(instance):
    if not isinstance(instance, str_types):
        return True
    try:
        return re.compile(instance)
    except re.error as e:
        raise ValueError('Error parsing regex: %s' % e)


@format_checker.checks('file', raises=ValueError)
def is_file(instance):
    if not isinstance(instance, str_types):
        return True
    if os.path.isfile(os.path.expanduser(instance)):
        return True
    raise ValueError('`%s` does not exist' % instance)


@format_checker.checks('path', raises=ValueError)
def is_path(instance):
    if not isinstance(instance, str_types):
        return True
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
    if not isinstance(instance, str_types):
        return True
    regexp = ('(' + '|'.join(['ftp', 'http', 'https', 'file', 'udp']) +
              '):\/\/(\w+:{0,1}\w*@)?(\S+)(:[0-9]+)?(\/|\/([\w#!:.?+=&%@!\-\/]))?')
    return re.match(regexp, instance)


def set_error_message(error):
    """
    Create user facing error message from a :class:`jsonschema.ValidationError` `error`

    """
    # First, replace default error messages with our custom ones
    if error.validator == 'type':
        if isinstance(error.validator_value, basestring):
            valid_types = [error.validator_value]
        else:
            valid_types = list(error.validator_value)
        # Replace some types with more pythony ones
        replace = {'object': 'dict', 'array': 'list'}
        valid_types = [replace.get(t, t) for t in valid_types]
        # Make valid_types into an english list, with commas and 'or'
        valid_types = ', '.join(valid_types[:-2] + ['']) + ' or '.join(valid_types[-2:])
        if isinstance(error.instance, dict):
            error.message = 'Got a dict, expected: %s' % valid_types
        if isinstance(error.instance, list):
            error.message = 'Got a list, expected: %s' % valid_types
        error.message = 'Got `%s`, expected: %s' % (error.instance, valid_types)
    elif error.validator == 'format':
        if error.cause:
            error.message = unicode(error.cause)
    elif error.validator == 'enum':
        error.message = 'Must be one of the following: %s' % ', '.join(map(unicode, error.validator_value))
    elif error.validator == 'additionalProperties':
        if error.validator_value is False:
            extras = set(jsonschema._utils.find_additional_properties(error.instance, error.schema))
            if len(extras) == 1:
                error.message = 'The key `%s` is not valid here.' % extras.pop()
            else:
                error.message = 'The keys %s are not valid here.' % ', '.join('`%s`' % e for e in extras)
    else:
        # Remove u'' string representation from jsonschema error messages
        error.message = re.sub('u\'(.*?)\'', '`\\1`', error.message)

    # Then update with any custom error message supplied from the schema
    custom_error = error.schema.get('error_%s' % error.validator, error.schema.get('error'))
    if custom_error:
        error.message = template.render(custom_error, error.__dict__)


def select_child_errors(validator, errors):
    """
    Looks through subschema errors, if any subschema is determined to be the intended one,
    (based on 'type' keyword errors,) errors from its branch will be released instead of the parent error.
    """
    for error in errors:
        if not error.context:
            yield error
            continue
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
                    if validator.is_type(e.validator_value, 'string'):
                        valid_types.add(e.validator_value)
                    else:
                        valid_types.update(e.validator_value)
        if not no_type_errors:
            # If all of the branches had a 'type' error, create our own virtual type error with all possible types
            for e in validator.descend(error.instance, {'type': valid_types}):
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


def validate_properties_w_defaults(validator, properties, instance, schema):

    if not validator.is_type(instance, 'object'):
        return
    for key, subschema in properties.iteritems():
        if 'default' in subschema:
            instance.setdefault(key, subschema['default'])
    for error in jsonschema.Draft4Validator.VALIDATORS["properties"](validator, properties, instance, schema):
        yield error


def validate_anyOf(validator, anyOf, instance, schema):
    errors = jsonschema.Draft4Validator.VALIDATORS["anyOf"](validator, anyOf, instance, schema)
    for e in select_child_errors(validator, errors):
        yield e


def validate_oneOf(validator, oneOf, instance, schema):
    errors = jsonschema.Draft4Validator.VALIDATORS["oneOf"](validator, oneOf, instance, schema)
    for e in select_child_errors(validator, errors):
        yield e


validators = {
    'anyOf': validate_anyOf,
    'oneOf': validate_oneOf
}

SchemaValidator = jsonschema.validators.extend(jsonschema.Draft4Validator, validators)