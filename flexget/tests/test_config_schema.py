from datetime import timedelta

import jsonschema

from flexget import config_schema


def iter_registered_schemas():
    for path in config_schema.schema_paths:
        schema = config_schema.resolve_ref(path)
        yield path, schema


class TestSchemaValidator:
    def test_registered_schemas_are_valid(self):
        for path, schema in iter_registered_schemas():
            try:
                config_schema.SchemaValidator.check_schema(schema)
            except jsonschema.SchemaError as e:
                raise AssertionError(
                    'plugin `{}` has an invalid schema. {} {} {}'.format(
                        path, '/'.join(str(p) for p in e.path), e.validator, e.message
                    )
                )
            except Exception as e:
                raise AssertionError(f'plugin `{path}` has an invalid schema. {e}')

    def test_refs_in_schemas_are_resolvable(self):
        def refs_in(item):
            if isinstance(item, dict):
                for key, value in item.items():
                    if key == '$ref':
                        yield value
                    else:
                        yield from refs_in(value)
            elif isinstance(item, list):
                for i in item:
                    yield from refs_in(i)

        registry = config_schema.Registry()
        for path, schema in iter_registered_schemas():
            resolver = registry.resolver(base_uri=path)
            for ref in refs_in(schema):
                assert resolver.lookup(ref)

    def test_resolves_local_refs(self):
        schema = {'$ref': '/schema/plugin/accept_all'}
        # accept_all schema should be for type boolean
        assert not config_schema.process_config(True, schema)
        assert config_schema.process_config(14, schema)

    def test_custom_format_checker(self):
        schema = {'type': 'string', 'format': 'quality'}
        assert not config_schema.process_config('720p', schema)
        assert config_schema.process_config('aoeu', schema)

    def test_custom_error(self):
        schema = {'type': 'string', 'error': 'This is not okay'}
        errors = config_schema.process_config(13, schema)
        assert errors[0].message == schema['error']

    def test_custom_error_template(self):
        schema = {
            'type': 'string',
            'minLength': 10,
            'error': '{{validator}} failed for {{instance}}',
        }
        errors = config_schema.process_config(13, schema)
        assert errors[0].message == "type failed for 13"
        errors = config_schema.process_config('aoeu', schema)
        assert errors[0].message == "minLength failed for aoeu"

    def test_custom_keyword_error(self):
        schema = {'type': 'string', 'error_type': 'This is not okay'}
        errors = config_schema.process_config(13, schema)
        assert errors[0].message == schema['error_type']

    def test_custom_keyword_error_overrides(self):
        schema = {'type': 'string', 'error_type': 'This is not okay', 'error': 'This is worse'}
        errors = config_schema.process_config(13, schema)
        assert errors[0].message == schema['error_type']

    def test_error_with_path(self):
        schema = {'properties': {'p': {'items': {'type': 'string', 'error': 'ERROR'}}}}
        errors = config_schema.process_config({'p': [13]}, schema)
        assert errors[0].json_pointer == '/p/0'
        assert errors[0].message == 'ERROR'

    def test_builtin_error_rewriting(self):
        schema = {'type': 'object'}
        errors = config_schema.process_config(42, schema)
        # We don't call them objects around here
        assert 'object' not in errors[0].message
        assert 'dict' in errors[0].message

    def test_anyOf_branch_is_chosen_based_on_type_errors(self):
        schema = {
            "anyOf": [
                {"type": ["string", "array"]},
                {"anyOf": [{"type": "integer"}, {"type": "number", "minimum": 5}]},
            ]
        }
        # If there are type errors on both sides, it should be a virtual type error with all types
        errors = config_schema.process_config(True, schema)
        assert len(errors) == 1
        assert tuple(errors[0].schema_path) == ('anyOf', 'type')
        # It should have all the types together
        assert set(errors[0].validator_value) == {'string', 'array', 'number', 'integer'}
        # If there are no type errors going down one branch it should choose it
        errors = config_schema.process_config(1.5, schema)
        assert len(errors) == 1
        assert errors[0].validator == 'minimum'

    def test_oneOf_branch_is_chosen_based_on_type_errors(self):
        schema = {
            "oneOf": [
                {"type": ["string", "array"]},
                {"oneOf": [{"type": "integer"}, {"type": "number", "minimum": 5}]},
            ]
        }
        errors = config_schema.process_config(True, schema)
        # If there are type errors on both sides, it should be a virtual type error with all types
        assert len(errors) == 1
        assert tuple(errors[0].schema_path) == ('oneOf', 'type')
        # It should have all the types together
        assert set(errors[0].validator_value) == {'string', 'array', 'number', 'integer'}
        # If there are no type errors going down one branch it should choose it
        errors = config_schema.process_config(1.5, schema)
        assert len(errors) == 1
        assert errors[0].validator == 'minimum'

    def test_defaults_are_filled(self):
        schema = {"properties": {"p": {"default": 5}}}
        config = {}
        config_schema.process_config(config, schema)
        assert config["p"] == 5

    def test_defaults_does_not_override_explicit_value(self):
        schema = {"properties": {"p": {"default": 5}}}
        config = {"p": "foo"}
        config_schema.process_config(config, schema)
        assert config["p"] == "foo"


class TestSchemaFormats:
    def _test_format(self, format, items, invalid=False):
        failures = []
        for item in items:
            try:
                config_schema.format_checker.check(item, format)
                if invalid:
                    failures.append(f"'{item}' should not be a valid '{format}")
            except jsonschema.FormatError as e:
                if not invalid:
                    failures.append(e.message)
        return failures

    def test_format_size(self):
        valid_sizes = [
            '100 MB',  # Spaces
            '100 MiB',  # Spaces
            '100 mib',  # Lowercase
            1048576,  # bytes as int
            '1048576',  # bytes as string
            '20.5GB',  # decimal
            '100KiB',
            '100KB',
            '100MiB',
            '100MB',
            '20GiB',
            '20GB',
            '2TiB',
            '2TB',
        ]

        invalid_sizes = ['1AiB', '1bytes', '1megabytes', '1gig', '1gigabytes']

        failures = self._test_format('size', valid_sizes)
        failures.extend(self._test_format('size', invalid_sizes, invalid=True))

        assert not failures, '{} failures:\n{}'.format(len(failures), '\n'.join(failures))

    def test_format_interval(self):
        valid_intervals = ['3 days', '12 hours', '1 minute']

        invalid_intervals = ['aoeu', '14', '3 dayz', 'about 5 minutes']

        failures = self._test_format('interval', valid_intervals)
        failures.extend(self._test_format('interval', invalid_intervals, invalid=True))

        assert not failures, '{} failures:\n{}'.format(len(failures), '\n'.join(failures))

    def test_format_percent(self):
        valid_percent = ['1%', '1 %', '70.05 %']

        invalid_percent = ['%5', 'abc%']

        failures = self._test_format('percent', valid_percent)
        failures.extend(self._test_format('percent', invalid_percent, invalid=True))

        assert not failures, '{} failures:\n{}'.format(len(failures), '\n'.join(failures))


class TestFormatParsers:
    def _test_parser(self, parser, items):
        failures = []
        for item in items:
            value = parser(item[0])
            if value != item[1]:
                failures.append(f'`{item[0]}` should parse to `{item[1]}` not `{value}`')
        return failures

    def test_parser_size(self):
        size_tests = [
            ('100 MB', 104857600),  # Space
            ('100 MiB', 104857600),  # Spaces
            ('100 mib', 104857600),  # Lowercase
            (1048576, 1048576),  # bytes as int
            ('1048576', 1048576),  # bytes as string
            ('20.5GB', 22011707392),  # decimal
            ('100KiB', 102400),
            ('100KB', 102400),
            ('100MiB', 104857600),
            ('100MB', 104857600),
            ('20GiB', 21474836480),
            ('20GB', 21474836480),
            ('2TiB', 2199023255552),
            ('2TB', 2199023255552),
        ]

        failures = self._test_parser(config_schema.parse_size, size_tests)

        assert not failures, '{} failures:\n{}'.format(len(failures), '\n'.join(failures))

    def test_parser_interval(self):
        intervals_tests = [
            ('3 days', timedelta(days=3)),
            ('12 hours', timedelta(hours=12)),
            ('1 minute', timedelta(seconds=60)),
        ]

        failures = self._test_parser(config_schema.parse_interval, intervals_tests)

        assert not failures, '{} failures:\n{}'.format(len(failures), '\n'.join(failures))

    def test_parser_percent(self):
        percent_tests = [('3%', 3.0), ('30.05%', 30.05), ('30 %', 30.0)]

        failures = self._test_parser(config_schema.parse_percent, percent_tests)

        assert not failures, '{} failures:\n{}'.format(len(failures), '\n'.join(failures))
