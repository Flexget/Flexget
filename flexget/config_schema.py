import datetime
import functools
import os
import re
from collections import defaultdict
from json import JSONDecodeError
from json import loads as json_loads
from re import Match, Pattern
from typing import Any, Callable, Optional, Union
from urllib.parse import parse_qsl, urlparse

import jsonschema
from jsonschema import ValidationError
from loguru import logger
from referencing import Registry as _Registry
from referencing import Resource
from referencing.exceptions import Unresolvable

from flexget import options
from flexget.event import event, fire_event
from flexget.terminal import console
from flexget.utils import json, qualities, template
from flexget.utils.template import get_template
from flexget.utils.tools import parse_episode_identifier, parse_filesize, parse_timedelta

logger = logger.bind(name='config_schema')

BASE_SCHEMA_NAME = 'draft2020-12'
BASE_SCHEMA_URI = 'https://json-schema.org/draft/2020-12/schema'
BaseValidator = jsonschema.Draft202012Validator
# Type hint for json schemas. (If we upgrade to a newer json schema version, the type might allow more than dicts.)
JsonSchema = Union[dict[str, Any], bool]
schema_paths: dict[str, Union[JsonSchema, Callable[..., JsonSchema]]] = {}


class ConfigValidationError(ValidationError):
    json_pointer: str


class ConfigError(ValueError):
    errors: list[ConfigValidationError]


# TODO: Rethink how config key and schema registration work
def register_schema(path: str, schema: Union[JsonSchema, Callable[..., JsonSchema]]):
    """
    Register `schema` to be available at `path` for $refs

    :param path: Path to make schema available
    :param schema: The schema, or function which returns the schema
    """
    schema_paths[path] = schema


# Validator that handles root structure of config.
_root_config_schema: Optional[JsonSchema] = None


def register_config_key(key: str, schema: JsonSchema, required: bool = False):
    """Registers a valid root level key for the config.

    :param string key:
      Name of the root level key being registered.
    :param dict schema:
      Schema for the key.
    :param bool required:
      Specify whether this is a mandatory key.
    """
    root_schema = get_schema()
    root_schema['properties'][key] = schema
    if required:
        root_schema.setdefault('required', []).append(key)
    register_schema(f'/schema/config/{key}', schema)


def get_schema() -> JsonSchema:
    global _root_config_schema
    if _root_config_schema is None:
        _root_config_schema = {
            'type': 'object',
            'properties': {},
            'additionalProperties': False,
            '$schema': BASE_SCHEMA_URI,
        }
        fire_event('config.register')
        # TODO: Is /schema/config this the best place for this?
        register_schema('/schema/config', _root_config_schema)
    return _root_config_schema


def one_or_more(schema: JsonSchema, unique_items: bool = False) -> JsonSchema:
    """
    Helper function to construct a schema that validates items matching `schema` or an array
    containing items matching `schema`.

    """

    schema.setdefault('title', 'single value')
    default = schema.pop('default', None)
    result = {
        'oneOf': [
            {
                'title': 'multiple values',
                'type': 'array',
                'items': schema,
                'minItems': 1,
                'uniqueItems': unique_items,
            },
            schema,
        ]
    }
    if default:
        result['default'] = default
    return result


def resolve_ref(uri: str) -> JsonSchema:
    """
    Finds and returns a schema pointed to by `uri` that has been registered in the register_schema function.
    """
    parsed = urlparse(uri)
    if parsed.path in schema_paths:
        schema = schema_paths[parsed.path]
        if callable(schema):
            schema = schema(**dict(parse_qsl(parsed.query)))
        return {'$schema': BASE_SCHEMA_URI, **schema}
    raise Unresolvable(f"{uri} could not be resolved")


def retrieve_resource(uri: str) -> Resource:
    return Resource.from_contents(resolve_ref(uri))


def process_config(
    config: Any, schema: Optional[JsonSchema] = None, set_defaults: bool = True
) -> list[ConfigValidationError]:
    """
    Validates the config, and sets defaults within it if `set_defaults` is set.
    If schema is not given, uses the root config schema.

    :returns: A list with :class:`jsonschema.ValidationError`s if any

    """
    if schema is None:
        schema = get_schema()

    registry = Registry()
    if set_defaults:
        # Use the jsonschema 'validates' decorator to make sure our custom behavior continues across $refs
        # which declare a $schema. https://github.com/python-jsonschema/jsonschema/issues/994
        jsonschema.validators.validates(f'{BASE_SCHEMA_NAME} w defaults')(SchemaValidatorWDefaults)
        validator = SchemaValidatorWDefaults(
            schema, registry=registry, format_checker=format_checker
        )
    else:
        validator = SchemaValidator(schema, registry=registry, format_checker=format_checker)
    try:
        errors: list[ValidationError] = list(validator.iter_errors(config))
    finally:
        # Make sure we don't leave the default setting validator installed
        jsonschema.validators.validates(BASE_SCHEMA_NAME)(SchemaValidator)
    # Customize the error messages
    for e in errors:
        set_error_message(e)
        e.json_pointer = '/' + '/'.join(map(str, e.path))
    return errors


def parse_time(time_string: str) -> datetime.time:
    """Parse a time string from the config into a :class:`datetime.time` object."""
    formats = ['%I:%M %p', '%H:%M', '%H:%M:%S']
    for f in formats:
        try:
            return datetime.datetime.strptime(time_string, f).time()
        except ValueError:
            continue
    raise ValueError(f'invalid time `{time_string}`')


def parse_interval(interval_string: str) -> datetime.timedelta:
    """Takes an interval string from the config and turns it into a :class:`datetime.timedelta` object."""
    regexp = r'^\d+ (second|minute|hour|day|week)s?$'
    if not re.match(regexp, interval_string):
        raise ValueError("should be in format 'x (seconds|minutes|hours|days|weeks)'")
    return parse_timedelta(interval_string)


def parse_percent(percent_input: str) -> float:
    """Takes a percent string from the config and turns it into a float."""
    percent_input = percent_input.rstrip('%')
    try:
        return float(percent_input)
    except ValueError:
        raise ValueError("should be in format '0-x%'")


def parse_size(size_input: str, si: bool = False) -> int:
    """Takes a size string from the config and turns it into int(bytes)."""
    try:
        # Bytes
        return int(size_input)
    except ValueError:
        return parse_filesize(size_input, si=si)


# Public API end here, the rest should not be used outside this module


Registry = functools.partial(_Registry, retrieve=retrieve_resource)


format_checker = jsonschema.FormatChecker(('email',))


@format_checker.checks('quality', raises=ValueError)
def is_quality(instance):
    if not isinstance(instance, str):
        return True
    return qualities.get(instance)


@format_checker.checks('quality_requirements', raises=ValueError)
def is_quality_req(instance):
    if not isinstance(instance, str):
        return True
    return qualities.Requirements(instance)


@format_checker.checks('time', raises=ValueError)
def is_time(time_string) -> bool:
    if not isinstance(time_string, str):
        return True
    return parse_time(time_string) is not None


@format_checker.checks('interval', raises=ValueError)
def is_interval(interval_string) -> bool:
    if not isinstance(interval_string, str):
        return True
    return parse_interval(interval_string) is not None


@format_checker.checks('size', raises=ValueError)
def is_size(size_string) -> bool:
    if not isinstance(size_string, (str, int)):
        return True
    return parse_size(size_string) is not None


@format_checker.checks('percent', raises=ValueError)
def is_percent(percent_string) -> bool:
    if not isinstance(percent_string, str):
        return True
    return parse_percent(percent_string) is not None


@format_checker.checks('regex', raises=ValueError)
def is_regex(instance) -> Union[bool, Pattern]:
    if not isinstance(instance, str):
        return True
    try:
        return re.compile(instance)
    except re.error as e:
        raise ValueError(f'Error parsing regex: {e}')


@format_checker.checks('file', raises=ValueError)
def is_file(instance) -> bool:
    if not isinstance(instance, str):
        return True
    if os.path.isfile(os.path.expanduser(instance)):
        return True
    raise ValueError(f'`{instance}` does not exist')


@format_checker.checks('path', raises=ValueError)
def is_path(instance) -> bool:
    if not isinstance(instance, str):
        return True
    # Only validate the part of the path before the first identifier to be replaced
    pat = re.compile(r'{[{%].*[}%]}')
    result = pat.search(instance)
    if result:
        instance = os.path.dirname(instance[0 : result.start()])
    if os.path.isdir(os.path.expanduser(instance)):
        return True
    raise ValueError(f'`{instance}` does not exist')


# TODO: jsonschema has a format checker for uri if rfc3987 is installed, perhaps we should use that
@format_checker.checks('url')
def is_url(instance) -> Union[None, bool, Match]:
    if not isinstance(instance, str):
        return True
    # Allow looser validation if this appears to start with jinja
    if instance.startswith('{{') or instance.startswith('{%'):
        return True
    regexp = (
        '('
        + '|'.join(['ftp', 'http', 'https', 'file', 'udp', 'socks5h?'])
        + r'):\/\/(\w+:{0,1}\w*@)?(\S+)(:[0-9]+)?(\/|\/([\w#!:.?+=&%@!\-\/]))?'
    )
    return re.match(regexp, instance)


@format_checker.checks('episode_identifier', raises=ValueError)
def is_episode_identifier(instance) -> bool:
    if not isinstance(instance, (str, int)):
        return True
    return parse_episode_identifier(instance) is not None


@format_checker.checks('episode_or_season_id', raises=ValueError)
def is_episode_or_season_id(instance):
    if not isinstance(instance, (str, int)):
        return True
    return parse_episode_identifier(instance, identify_season=True) is not None


@format_checker.checks('file_template', raises=ValueError)
def is_valid_template(instance) -> bool:
    if not isinstance(instance, str):
        return True
    return get_template(instance) is not None


@format_checker.checks('json', raises=ValueError)
def is_json(instance) -> bool:
    if not isinstance(instance, str):
        return False

    try:
        json_loads(instance)
    except JSONDecodeError:
        raise ValueError(f'`{instance}` is not a valid json')

    return True


def set_error_message(error: jsonschema.ValidationError) -> None:
    """
    Create user facing error message from a :class:`jsonschema.ValidationError` `error`

    """
    # First, replace default error messages with our custom ones
    if error.validator == 'type':
        if isinstance(error.validator_value, str):
            valid_types_list = [error.validator_value]
        else:
            valid_types_list = list(error.validator_value)
        # Replace some types with more pythony ones
        replace = {'object': 'dict', 'array': 'list'}
        valid_types_list = [replace.get(t, t) for t in valid_types_list]
        # Make valid_types into an english list, with commas and 'or'
        valid_types = ', '.join(valid_types_list[:-2] + ['']) + ' or '.join(valid_types_list[-2:])
        if isinstance(error.instance, dict):
            error.message = f'Got a dict, expected: {valid_types}'
        if isinstance(error.instance, list):
            error.message = f'Got a list, expected: {valid_types}'
        error.message = f'Got `{error.instance}`, expected: {valid_types}'
    elif error.validator == 'format':
        if error.cause:
            error.message = str(error.cause)
    elif error.validator == 'enum':
        error.message = 'Must be one of the following: {}'.format(
            ', '.join(map(str, error.validator_value))
        )
    elif error.validator == 'additionalProperties':
        if error.validator_value is False:
            extras = set(
                jsonschema._utils.find_additional_properties(error.instance, error.schema)
            )
            if len(extras) == 1:
                error.message = f'The key `{extras.pop()}` is not valid here.'
            else:
                error.message = 'The keys {} are not valid here.'.format(
                    ', '.join(f'`{e}`' for e in extras)
                )
    else:
        # Remove u'' string representation from jsonschema error messages
        error.message = re.sub('u\'(.*?)\'', '`\\1`', error.message)

    # Then update with any custom error message supplied from the schema
    custom_error = error.schema.get(f'error_{error.validator}', error.schema.get('error'))
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
        for i, errors in subschema_errors.items():
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
            for e in next(iter(no_type_errors.values())):
                e.schema_path.extendleft(reversed(error.schema_path))
                e.path.extendleft(reversed(error.path))
                yield e
        else:
            yield error


def validate_properties_w_defaults(validator, properties, instance, schema):
    if not validator.is_type(instance, 'object'):
        return
    for key, subschema in properties.items():
        if 'default' in subschema:
            instance.setdefault(key, subschema['default'])
    yield from BaseValidator.VALIDATORS["properties"](validator, properties, instance, schema)


def validate_anyOf(validator, anyOf, instance, schema):
    errors = BaseValidator.VALIDATORS["anyOf"](validator, anyOf, instance, schema)
    yield from select_child_errors(validator, errors)


def validate_oneOf(validator, oneOf, instance, schema):
    errors = BaseValidator.VALIDATORS["oneOf"](validator, oneOf, instance, schema)
    yield from select_child_errors(validator, errors)


def validate_deprecated(validator, deprecated, instance, schema):
    if "deprecationMessage" not in schema and isinstance(deprecated, str):
        logger.warning(deprecated)


def validate_deprecationMessage(validator, message, instance, schema):
    """Not really a validator, just warns if deprecated section of config is being used."""
    logger.warning(message)


validators = {
    'anyOf': validate_anyOf,
    'oneOf': validate_oneOf,
    'deprecated': validate_deprecated,
    'deprecationMessage': validate_deprecationMessage,
}

SchemaValidator = jsonschema.validators.extend(BaseValidator, validators)
jsonschema.validators.validates(BASE_SCHEMA_NAME)(SchemaValidator)
SchemaValidatorWDefaults = jsonschema.validators.extend(
    SchemaValidator, {'properties': validate_properties_w_defaults}
)


def deep_in(path: str, dictionary: dict) -> bool:
    for part in path.split('/'):
        if part not in dictionary:
            return False
        dictionary = dictionary[part]
    return True


def deep_set(path: str, dictionary: dict, value: Any) -> None:
    parts = path.split('/')
    for part in parts[:-1]:
        dictionary = dictionary.setdefault(part, {})
    dictionary[parts[-1]] = value


def _rewrite_ref(identifier: str, definition_path: str, defs: dict) -> str:
    """
    The refs in the schemas are arbitrary identifiers, and cannot be used as-is as real network locations.
    This rewrites any of those arbitrary refs to be real urls servable by this endpoint.
    """
    if identifier.startswith('/schema/'):
        path = identifier[len('/schema/') :]
        if not deep_in(path, defs):
            new_def = resolve_ref(identifier)
            new_def.pop('$schema', None)
            # We have to set this before we recurse to stop infinite recursion
            deep_set(path, defs, new_def)
            deep_set(path, defs, _inline_refs(new_def, path, defs))
        return "#/$defs/" + path
    if identifier.startswith('#'):
        return "#/$defs/" + definition_path + identifier[1:]
    return identifier


def _inline_refs(schema: JsonSchema, definition_path: str, defs: dict) -> Union[JsonSchema, list]:
    if isinstance(schema, dict):
        if '$ref' in schema:
            return {**schema, '$ref': _rewrite_ref(schema['$ref'], definition_path, defs)}
        return {k: _inline_refs(v, definition_path, defs) for k, v in schema.items()}
    if isinstance(schema, list):
        return [_inline_refs(v, definition_path, defs) for v in schema]
    return schema


def inline_refs(schema: JsonSchema) -> JsonSchema:
    """Includes all $refs to subschemas in the $defs section of the schema, and rewrites
    the $refs to point to the right place."""
    definitions = {}
    schema = _inline_refs(schema, "", definitions)
    schema.setdefault('$defs', {}).update(definitions)
    return schema


def export_schema(manager, namespace):
    schema = inline_refs(get_schema())
    if namespace.output_file:
        with open(namespace.output_file, 'w') as f:
            f.write(json.dumps(schema, indent=2))
        console(f'Schema written to {namespace.output_file}')
        return
    console(json.dumps(schema, indent=2))


@event('options.register')
def register_parser_arguments():
    parser = options.register_command(
        'export-schema',
        export_schema,
        help='Output the JSON schema for the config',
    )
    parser.add_argument('--output-file', '-o', help='Write the exported schema to the given file')
