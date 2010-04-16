import logging
import re
from flexget.plugin import *

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
          [rest]: <operation>   # non matching entries are
        
        Possible operations: accept, reject, accept_excluding, reject_excluding        
    """

    def validator(self):
        from flexget import validator

        def build_list(regexps):
            regexps.accept('regexp')
            
            # bundle is a dictionary form
            bundle = regexps.accept('dict')
            # path as a single parameter
            bundle.accept_any_key('text') 
            
            # advanced configuration as a parameter
            advanced = bundle.accept_any_key('dict')
            advanced.accept('text', key='path') # TODO: text -> path
            # accept set parameters
            set = advanced.accept('dict', key='set')
            set.accept_any_key('any')
            # not as a single parameter
            advanced.accept('regexp', key='not')
            # from as a single parameter
            advanced.accept('text', key='from')
            
            # not in a list form
            advanced.accept('list', key='not').accept('regexp')

            # from in a list form
            advanced.accept('list', key='from').accept('text')
            
        conf = validator.factory('dict')
        for operation in ['accept', 'reject', 'accept_excluding', 'reject_excluding']:
            regexps = conf.accept('list', key=operation)
            build_list(regexps)
            
        conf.accept('text', key='rest') # TODO: accept only ['accept','filter','reject']
        return conf

    @priority(172)
    def on_feed_filter(self, feed):
        match_methods = {'accept': feed.accept, 'reject': feed.reject}
        non_match_methods = {'accept_excluding': feed.accept, 'reject_excluding': feed.reject}
        
        # TODO: what if accept and accept_excluding configured? Should raise error ...

        rest = []
        config = feed.config.get('regexp', {})
        for operation, regexps in config.iteritems():
            if operation == 'rest':
                continue
            match_method = match_methods.get(operation, None)
            non_match_method = non_match_methods.get(operation, None)
            r = self.filter(feed, match_method, non_match_method, regexps)
            if isinstance(r, list):
                rest.extend(r)
            
        if 'rest' in config:
            rest_method = match_methods.get(config['rest'])
            if not rest_method:
                raise PluginWarning('Unknown operation %s' % config['rest'], log)
            for entry in rest:
                log.debug('Rest method %s for %s' % (rest_method.__name__, entry['title']))
                rest_method(entry)
        
    def matches(self, entry, regexp, find_from=[]):
        """Check if :entry: has any string fields that matches :regexp:.
        Optional :find_from: can be given to limit searching fields"""
        unquote = ['url']
        for field, value in entry.iteritems():
            if not isinstance(value, basestring):
                continue
            if find_from:
                if not field in find_from:
                    continue
            if field in unquote:
                import urllib
                value = urllib.unquote(value)
            if re.search(regexp, value, re.IGNORECASE | re.UNICODE):
                return field
        return None

    def filter(self, feed, match_method, non_match_method, regexps):
        """
            match_method - method is called with a entry as a parameter when entry matches
            non_match_method - method is called with a entry as a parameter when entry does NOT match
            regepx - list of regular expressions
            
            Return list of entries that didn't match regexps or None if match_method and non_match_method were given
        """
        rest = []
        for entry in feed.entries:
            match = False
            for regexp_raw in regexps:
                # set custom path for entry if pattern specifies one
                path = None
                setconfig = {}
                secondary = []
                from_fields = []
                if isinstance(regexp_raw, dict):
                    #log.debug('complex regexp: %s' % regexp_raw)
                    regexp_raw, value = regexp_raw.items()[0]
                    # advanced configuration
                    if isinstance(value, dict):
                        path = value.get('path', None)
                        setconfig = value.get('set', {})
                        from_fields = value.get('from', [])
                        if 'not' in value:
                            if isinstance(value['not'], list): 
                                secondary.extend(value['not'])
                            else: 
                                secondary.append(value['not'])
                    else:
                        path = value

                # check if entry matches given regexp
                field = self.matches(entry, regexp_raw, from_fields)
                if field:
                    match = True
                    # if we have secondary (not) regexps, test them
                    for secondary_re in secondary:
                        if self.matches(entry, secondary_re):
                            log.debug("Secondary filter regexp '%s' matched '%s'" % (entry['title'], secondary_re))
                            match = False
                            
                if match:
                    if path:
                        entry['path'] = path
                    if setconfig:
                        log.debug('adding set: info to entry:"%s" %s' % (entry['title'], setconfig))
                        set = get_plugin_by_name('set')
                        set.instance.modify(entry, setconfig)
                    log.debug('regexp %s matched to field %s' % (regexp_raw, field))
                    break
                    
            if match:
                if match_method:
                    match_method(entry, 'regexp %s matched to field %s' % (regexp_raw, field))
                else:
                    rest.append(entry)
            else:
                if non_match_method:
                    non_match_method(entry)
                else:
                    rest.append(entry)

        if not (match_method and non_match_method):
            return rest
        else:
            return None

register_plugin(FilterRegexp, 'regexp')
