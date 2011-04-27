import logging
import re
from flexget.plugin import register_plugin, priority, get_plugin_by_name

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

    def validator(self):
        from flexget import validator

        def build_list(regexps):
            regexps.accept('regexp')

            # bundle is a dictionary form
            bundle = regexps.accept('dict')
            value_validator = bundle.accept_valid_keys('root', key_type='regexp')
            # path as a single parameter
            value_validator.accept('path', allow_replacement=True)

            # advanced configuration as a parameter
            advanced = value_validator.accept('dict')
            advanced.accept('path', key='path', allow_replacement=True)
            # accept set parameters
            set = advanced.accept('dict', key='set')
            set.accept_any_key('any')
            # not as a single parameter
            advanced.accept('regexp', key='not')
            # not in a list form
            advanced.accept('list', key='not').accept('regexp')
            # from as a single parameter
            advanced.accept('text', key='from')
            # from in a list form
            advanced.accept('list', key='from').accept('text')

        conf = validator.factory('dict')
        for operation in ['accept', 'reject', 'accept_excluding', 'reject_excluding']:
            regexps = conf.accept('list', key=operation)
            build_list(regexps)

        conf.accept('choice', key='rest').accept_choices(['accept', 'reject'])
        conf.accept('text', key='from')
        conf.accept('list', key='from').accept('text')
        return conf

    def prepare_config(self, config):
        """Returns the config in standard format.

        All regexps are turned into dictionaries in the form {regexp: options}

        Options is a dict that can (but may not) contain the following keys

            path: will be attached to entries that match
            set: a dict of values to be attached to entries that match via set plugin
            from: a list of fields in entry for the regexps to match against
            not: a list of regexps that if matching, will disqualify the main match
        """

        out_config = {}
        if 'rest' in config:
            out_config['rest'] = config['rest']
        # Turn all our regexps into advanced form dicts
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
                # advanced configuration
                if config.get('from'):
                    opts.setdefault('from', config['from'])
                # Put plain strings into list form for from and not
                if 'from' in opts and isinstance(opts['from'], basestring):
                    opts['from'] = [opts['from']]
                if 'not' in opts and isinstance(opts['not'], basestring):
                    opts['not'] = [opts['not']]
                # make sure regxp is a string for series like '24'
                regexp = unicode(regexp)
                out_config.setdefault(operation, []).append({regexp: opts})
        return out_config

    @priority(172)
    def on_feed_filter(self, feed, config):
        # TODO: what if accept and accept_excluding configured? Should raise error ...
        config = self.prepare_config(config)
        rest = []
        for operation, regexps in config.iteritems():
            if operation == 'rest':
                continue
            r = self.filter(feed, operation, regexps)
            if not rest:
                rest = r
            else:
                # If there is already something in rest, take the intersection with r (entries no operations matched)
                rest = [entry for entry in r if entry in rest]

        if 'rest' in config:
            rest_method = feed.accept if config['rest'] == 'accept' else feed.reject
            for entry in rest:
                log.debug('Rest method %s for %s' % (config['rest'], entry['title']))
                rest_method(entry, 'regexp `rest`')

    def matches(self, entry, regexp, find_from=None, not_regexps=None):
        """Check if :entry: has any string fields or strings in a list field that match :regexp:.
        Optional :find_from: can be given as a list to limit searching fields"""
        unquote = ['url']
        for field in find_from or entry:
            if not entry.get(field):
                continue
            # Make all fields into lists to search
            values = entry[field]
            if not isinstance(values, list):
                values = [values]
            for value in values:
                if not isinstance(value, basestring):
                    continue
                if field in unquote:
                    import urllib
                    value = urllib.unquote(value)
                    # If none of the not_regexps match
                if re.search(regexp, value, re.IGNORECASE | re.UNICODE):
                    # Make sure the not_regexps do not match for this field
                    for not_regexp in not_regexps or []:
                        if self.matches(entry, not_regexp, find_from=[field]):
                            break
                    else: # None of the not_regexps matched
                        return field
        return None

    def filter(self, feed, operation, regexps):
        """
            operation - one of 'accept' 'reject' 'accept_excluding' and 'reject_excluding'
                accept and reject will be called on the entry if any of the regxps match
                _excluding operations will be called if any of the regexps don't match
            regexps - list of {regexp: options} dictionaries

            Return list of entries that didn't match regexps
        """
        rest = []
        method = feed.accept if 'accept' in operation else feed.reject
        match_mode = 'excluding' not in operation
        for entry in feed.entries:
            for regexp_opts in regexps:
                regexp, opts = regexp_opts.items()[0]

                # check if entry matches given regexp, also makes sure it doesn't match secondary
                field = self.matches(entry, regexp, opts.get('from'), opts.get('not'))
                # Run if we are in match mode and have a hit, or are in non-match mode and don't have a hit
                if match_mode == bool(field):
                    # Creates the string with the reason for the hit
                    matchtext = 'regexp \'%s\' ' % regexp + ('matched field \'%s\'' % field if match_mode else 'didn\'t match')
                    log.debug('%s for %s' % (matchtext, entry['title']))
                    # apply settings to entry and run the method on it
                    if opts.get('path'):
                        entry['path'] = opts['path']
                    if opts.get('set'):
                        # invoke set plugin with given configuration
                        log.debug('adding set: info to entry:"%s" %s' % (entry['title'], opts['set']))
                        set = get_plugin_by_name('set')
                        set.instance.modify(entry, opts['set'])
                    method(entry, matchtext)
                    # We had a match so break out of the regexp loop.
                    break
            else:
                # We didn't run method for any of the regexps, add this entry to rest
                rest.append(entry)
        return rest

register_plugin(FilterRegexp, 'regexp', api_ver=2)
