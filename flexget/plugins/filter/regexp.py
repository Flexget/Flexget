from __future__ import unicode_literals, division, absolute_import
import urllib
import logging
import re

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event

log = logging.getLogger('regexp')


class FilterRegexp(object):

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
            'from': one_or_more({'type': 'string'})
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
                                            'not': one_or_more({'type': 'string', 'format': 'regex'}),
                                            'from': one_or_more({'type': 'string'})
                                        },
                                        'additionalProperties': False
                                    }
                                ]
                            }
                        }
                    ]
                }
            }
        }
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
        for operation, regexps in config.iteritems():
            if operation in ['rest', 'from']:
                continue
            for regexp_item in regexps:
                if not isinstance(regexp_item, dict):
                    regexp = regexp_item
                    regexp_item = {regexp: {}}
                regexp, opts = regexp_item.items()[0]
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
                if 'from' in opts and isinstance(opts['from'], basestring):
                    opts['from'] = [opts['from']]
                if 'not' in opts and isinstance(opts['not'], basestring):
                    opts['not'] = [opts['not']]

                # compile `not` option regexps
                if 'not' in opts:
                    opts['not'] = [re.compile(not_re, re.IGNORECASE | re.UNICODE) for not_re in opts['not']]

                # compile regexp and make sure regexp is a string for series like '24'
                try:
                    regexp = re.compile(unicode(regexp), re.IGNORECASE | re.UNICODE)
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
        rest = []
        for operation, regexps in config.iteritems():
            if operation == 'rest':
                continue
            leftovers = self.filter(task, operation, regexps)
            if not rest:
                rest = leftovers
            else:
                # If there is already something in rest, take the intersection with r (entries no operations matched)
                rest = [entry for entry in leftovers if entry in rest]

        if 'rest' in config:
            rest_method = Entry.accept if config['rest'] == 'accept' else Entry.reject
            for entry in rest:
                log.debug('Rest method %s for %s' % (config['rest'], entry['title']))
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
        unquote = ['url']
        for field in find_from or ['title', 'description']:
            # Only evaluate lazy fields if find_from has been explicitly specified
            if not entry.get(field, eval_lazy=find_from):
                continue
            # Make all fields into lists for search purposes
            values = entry[field]
            if not isinstance(values, list):
                values = [values]
            for value in values:
                if not isinstance(value, basestring):
                    continue
                if field in unquote:
                    value = urllib.unquote(value)
                    # If none of the not_regexps match
                if regexp.search(value):
                    # Make sure the not_regexps do not match for this field
                    for not_regexp in not_regexps or []:
                        if self.matches(entry, not_regexp, find_from=[field]):
                            entry.trace('Configured not_regexp %s matched, ignored' % not_regexp)
                            break
                    else:  # None of the not_regexps matched
                        return field

    def filter(self, task, operation, regexps):
        """
        :param task: Task instance
        :param operation: one of 'accept' 'reject' 'accept_excluding' and 'reject_excluding'
                          accept and reject will be called on the entry if any of the regxps match
                          *_excluding operations will be called if any of the regexps don't match
        :param regexps: list of {compiled_regexp: options} dictionaries
        :return: Return list of entries that didn't match regexps
        """
        rest = []
        method = Entry.accept if 'accept' in operation else Entry.reject
        match_mode = 'excluding' not in operation
        for entry in task.entries:
            log.trace('testing %i regexps to %s' % (len(regexps), entry['title']))
            for regexp_opts in regexps:
                regexp, opts = regexp_opts.items()[0]

                # check if entry matches given regexp configuration
                field = self.matches(entry, regexp, opts.get('from'), opts.get('not'))

                # Run if we are in match mode and have a hit, or are in non-match mode and don't have a hit
                if match_mode == bool(field):
                    # Creates the string with the reason for the hit
                    matchtext = 'regexp \'%s\' ' % regexp.pattern + ('matched field \'%s\'' %
                                                                     field if match_mode else 'didn\'t match')
                    log.debug('%s for %s' % (matchtext, entry['title']))
                    # apply settings to entry and run the method on it
                    if opts.get('path'):
                        entry['path'] = opts['path']
                    if opts.get('set'):
                        # invoke set plugin with given configuration
                        log.debug('adding set: info to entry:"%s" %s' % (entry['title'], opts['set']))
                        set = plugin.get_plugin_by_name('set')
                        set.instance.modify(entry, opts['set'])
                    method(entry, matchtext)
                    # We had a match so break out of the regexp loop.
                    break
            else:
                # We didn't run method for any of the regexps, add this entry to rest
                entry.trace('None of configured %s regexps matched' % operation)
                rest.append(entry)
        return rest


@event('plugin.register')
def register_plugin():
    plugin.register(FilterRegexp, 'regexp', api_ver=2)
