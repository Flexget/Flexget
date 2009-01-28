import urllib
import logging
import re

__pychecker__ = 'unusednames=parser,feed'

log = logging.getLogger('regexp')

class FilterRegexp:

    """
        TODO: (see wiki for now)
    """
    
    def register(self, manager, parser):
        manager.register('regexp')

    def validate(self, config):
        """Validate given configuration"""
        from validator import DictValidator
        def conf(patterns):
            patterns.accept(str)
            patterns.accept(int)
            bundle = patterns.accept(dict)
            options = bundle.accept_any_key(dict)
            options.accept('path', str)
            options.accept('not', str)
            options.accept('not', int)
            nl = options.accept('not', list)
            nl.accept(str)
            nl.accept(int)
        root = DictValidator()
        for name in ['accept','filter','reject','accept_excluding','filter_excluding','reject_excluding']:
            sub = root.accept(name, list)
            conf(sub)
        root.accept('rest', ['accept','filter','reject'])
        root.validate(config)
        return root.errors.messages
        
    def feed_filter(self, feed):
        match_methods = {'accept': feed.accept, 'filter': feed.filter, 'reject': feed.reject }
        non_match_methods = {'accept_excluding': feed.accept, 'filter_excluding': feed.filter, 'reject_excluding': feed.reject }
        
        # TODO: what if accept and accept_excluding configured? Should raise error ...

        rest = []
        config = feed.config.get('regexp', {})
        for operation, regexps in config.iteritems():
            if operation=='rest': continue
            match_method = match_methods.get(operation, None)
            non_match_method = non_match_methods.get(operation, None)
            r = self.filter(feed, match_method, non_match_method, regexps)
            if isinstance(r, list):
                rest.extend(r)
            
        if config.has_key('rest'):
            rest_method = match_methods.get(config['rest'])
            for entry in rest:
                log.debug('Rest method %s for %s' % (rest_method.__name__, entry['title']))
                rest_method(entry)
        
    def matches(self, entry, regexp):
        """Return True if any of the entry string fields match given regexp"""
        regexp = str(regexp)
        unquote = ['url']
        for field, value in entry.iteritems():
            if not isinstance(value, basestring):
                continue
            if field in unquote:
                value = urllib.unquote(value)
            if re.search(regexp, value, re.IGNORECASE|re.UNICODE):
                return True

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
                secondary = []
                if isinstance(regexp_raw, dict):
                    #log.debug('complex regexp: %s' % regexp_raw)
                    regexp_raw, value = regexp_raw.items()[0]
                    # if regexp has dict as parameter
                    if isinstance(value, dict):
                        path = value.get('path', None)
                        if value.has_key('not'):
                            if isinstance(value['not'], list): 
                                secondary.extend(value['not'])
                            else: 
                                secondary.append(value['not'])
                    else:
                        path = value

                # check if entry matches given regexp
                if self.matches(entry, regexp_raw):
                    match = True
                    # if we have secondary (not) regexps, test them
                    for secondary_re in secondary:
                        if self.matches(entry, secondary_re):
                            log.debug("Secondary filter regexp '%s' matched '%s'" % (entry['title'], secondary_re))
                            match = False
                            
                if match:
                    if path: entry['path'] = path
                    log.debug("'%s' matched '%s'" % (entry['title'], regexp_raw))
                    break
                    
            if match:
                if match_method:
                    match_method(entry)
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