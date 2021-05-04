import re
from urllib.parse import unquote

from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event

logger = logger.bind(name='regexp')


class FilterRegexp:
    """
    All possible forms.

    regexp:
      [operation]:           # operation to perform on matches
        - [regexp]           # simple regexp
        - [regexp]: <path>   # override path
        - [regexp]:
            [path]: <path>   # override path
            [not]: <regexp>  # not match
            [from]: <field>  # search from given entry field
        - [regexp]:
            [path]: <path>   # override path
            [not]:           # list of not match regexps
              - <regexp>
            [from]:          # search only from these fields
              - <field>
      [operation]:
        - <regexp>
      [rest]: <operation>    # non matching entries are
      [from]:                # search only from these fields for all regexps
        - <field>

    Possible operations: accept, reject, accept_excluding, reject_excluding
    """

    schema = {
        'type': 'object',
        'properties': {
            'accept': {'$ref': '#/definitions/regex_list'},
            'reject': {'$ref': '#/definitions/regex_list'},
            'accept_excluding': {'$ref': '#/definitions/regex_list'},
            'reject_excluding': {'$ref': '#/definitions/regex_list'},
            'rest': {'type': 'string', 'enum': ['accept', 'reject']},
            'from': one_or_more({'type': 'string'}),
        },
        'additionalProperties': False,
        'definitions': {
            # The validator for a list of regexps, each with or without settings
            'regex_list': {
                'type': 'array',
                'items': {
                    'oneOf': [
                        # Plain regex string
                        {'type': 'string', 'format': 'regex'},
                        # Regex with options (regex is key, options are value)
                        {
                            'type': 'object',
                            'additionalProperties': {
                                'oneOf': [
                                    # Simple options, just path
                                    {'type': 'string', 'format': 'path'},
                                    # Dict style options
                                    {
                                        'type': 'object',
                                        'properties': {
                                            'path': {'type': 'string', 'format': 'path'},
                                            'set': {'type': 'object'},
                                            'not': one_or_more(
                                                {'type': 'string', 'format': 'regex'}
                                            ),
                                            'from': one_or_more({'type': 'string'}),
                                        },
                                        'additionalProperties': False,
                                    },
                                ]
                            },
                        },
                    ]
                },
            }
        },
    }

    def prepare_config(self, config):
        """Returns the config in standard format.

        All regexps are turned into dictionaries in the form of {compiled regexp: options}

        :param config: Dict that can optionally contain the following keys
            path: will be attached to entries that match
            set: a dict of values to be attached to entries that match via set plugin
            from: a list of fields in entry for the regexps to match against
            not: a list of compiled regexps that if matching, will disqualify the main match
        :return: New config dictionary
        """
        out_config = {}
        if 'rest' in config:
            out_config['rest'] = config['rest']
        # Turn all our regexps into advanced form dicts and compile them
        for operation, regexps in config.items():
            if operation in ['rest', 'from']:
                continue
            for regexp_item in regexps:
                if not isinstance(regexp_item, dict):
                    regexp = regexp_item
                    regexp_item = {regexp: {}}
                regexp, opts = list(regexp_item.items())[0]
                # Parse custom settings for this regexp
                if not isinstance(opts, dict):
                    opts = {'path': opts}
                else:
                    # We don't want to modify original config
                    opts = opts.copy()
                # advanced configuration
                if config.get('from'):
                    opts.setdefault('from', config['from'])
                # Put plain strings into list form for `from` and `not` options
                if 'from' in opts and isinstance(opts['from'], str):
                    opts['from'] = [opts['from']]
                if 'not' in opts and isinstance(opts['not'], str):
                    opts['not'] = [opts['not']]

                # compile `not` option regexps
                if 'not' in opts:
                    opts['not'] = [
                        re.compile(not_re, re.IGNORECASE | re.UNICODE) for not_re in opts['not']
                    ]

                # compile regexp and make sure regexp is a string for series like '24'
                try:
                    regexp = re.compile(str(regexp), re.IGNORECASE | re.UNICODE)
                except re.error as e:
                    # Since validator can't validate dict keys (when an option is defined for the pattern) make sure we
                    # raise a proper error here.
                    raise plugin.PluginError('Invalid regex `%s`: %s' % (regexp, e))
                out_config.setdefault(operation, []).append({regexp: opts})
        return out_config

    @plugin.priority(172)
    def on_task_filter(self, task, config):
        # TODO: what if accept and accept_excluding configured? Should raise error ...
        config = self.prepare_config(config)
        # Keep track of all entries which have not matched any regexp
        rest = set(task.entries)
        for operation, regexps in config.items():
            if operation == 'rest':
                continue
            matched = self.filter(task.entries, operation, regexps)
            # Remove any entries from rest which matched this regexp
            rest -= matched

        if 'rest' in config:
            rest_method = Entry.accept if config['rest'] == 'accept' else Entry.reject
            for entry in rest:
                logger.debug('Rest method {} for {}', config['rest'], entry['title'])
                rest_method(entry, 'regexp `rest`')

    def matches(self, entry, regexp, find_from=None, not_regexps=None):
        """
        Check if :entry: has any string fields or strings in a list field that match :regexp:

        :param entry: Entry instance
        :param regexp: Compiled regexp
        :param find_from: None or a list of fields to search from
        :param not_regexps: None or list of regexps that can NOT match
        :return: Field matching
        """
        unquote_fields = ['url']
        for field in find_from or ['title', 'description']:
            # Only evaluate lazy fields if find_from has been explicitly specified
            if not entry.get(field, eval_lazy=find_from):
                continue
            # Make all fields into lists for search purposes
            values = entry[field]
            if not isinstance(values, list):
                values = [values]
            for value in values:
                if not isinstance(value, str):
                    value = str(value)
                if field in unquote_fields:
                    value = unquote(value)
                    # If none of the not_regexps match
                if regexp.search(value):
                    # Make sure the not_regexps do not match for this field
                    for not_regexp in not_regexps or []:
                        if self.matches(entry, not_regexp, find_from=[field]):
                            entry.trace('Configured not_regexp %s matched, ignored' % not_regexp)
                            break
                    else:  # None of the not_regexps matched
                        return field

    def filter(self, entries, operation, regexps):
        """
        :param entries: entries to filter
        :param operation: one of 'accept' 'reject' 'accept_excluding' and 'reject_excluding'
                          accept and reject will be called on the entry if any of the regexps match
                          *_excluding operations will be called if any of the regexps don't match
        :param regexps: list of {compiled_regexp: options} dictionaries
        :return: Return set of entries that matched regexps
        """
        matched = set()
        method = Entry.accept if 'accept' in operation else Entry.reject
        match_mode = 'excluding' not in operation
        for entry in entries:
            logger.trace('testing {} regexps to {}', len(regexps), entry['title'])
            for regexp_opts in regexps:
                regexp, opts = list(regexp_opts.items())[0]

                # check if entry matches given regexp configuration
                field = self.matches(entry, regexp, opts.get('from'), opts.get('not'))

                # Run if we are in match mode and have a hit, or are in non-match mode and don't have a hit
                if match_mode == bool(field):
                    # Creates the string with the reason for the hit
                    matchtext = 'regexp \'%s\' ' % regexp.pattern + (
                        'matched field \'%s\'' % field if match_mode else 'didn\'t match'
                    )
                    logger.debug('{} for {}', matchtext, entry['title'])
                    # apply settings to entry and run the method on it
                    if opts.get('path'):
                        entry['path'] = opts['path']
                    if opts.get('set'):
                        # invoke set plugin with given configuration
                        logger.debug(
                            'adding set: info to entry:"{}" {}', entry['title'], opts['set']
                        )
                        plugin.get('set', self).modify(entry, opts['set'])
                    method(entry, matchtext)
                    matched.add(entry)
                    # We had a match so break out of the regexp loop.
                    break
            else:
                # We didn't run method for any of the regexps, add this entry to rest
                entry.trace('None of configured %s regexps matched' % operation)
        return matched


@event('plugin.register')
def register_plugin():
    plugin.register(FilterRegexp, 'regexp', api_ver=2)
