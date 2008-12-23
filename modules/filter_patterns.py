import urllib
import logging
import re

__pychecker__ = 'unusednames=parser,feed'

log = logging.getLogger('patterns')

class FilterPatterns:

    """
        Filter out entries based on regular expression matches.
        Configuration example:

        patterns:
          - regular expression
          - another reqular expression

        Advanced users:

        It's also possible to specify custom download path for
        pattern and secondary regexp(s) that causes entry to be
        filtered even when primary regexp matches entry.

        Examples:

        pattenrs:
          # simplest way to specify custom path
          - regexp1: ~/custom_path/

          # alternative way to specify custom path
          - regexp2:
              path: ~/custom_path/

          # specify custom path and secondary single filter regexp
          - regexp2:
              path: ~/custom_path/
              not: regexp3

          # multiple secondary filter regexps
          - regexp4:
              not:
                - regexp5
                - regexp6

          # Tip: In yaml you can write dictionaries and lists in inline form.
          # Above examples can be written also as:
          - regexp2: {path: ~/custom_path/, not: regexp3}
          - regexp4: {not: [regexp5, regexp6]}
    """

    
    def register(self, manager, parser):
        manager.register('patterns')
#        parser.add_option("--try-pattern", action="store", dest="try_pattern", default=None,
#                          help="Run with given pattern. Useful to try out matching with --test.")

    def validate(self, config):
        """Validate given configuration"""
        from validator import ListValidator
        patterns = ListValidator()
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
        patterns.validate(config)
        return patterns.errors.messages

    def matches(self, entry, regexp):
        """Return True if any of the entry fields match given regexp"""
        regexp = str(regexp)
        unquote = ['url']
        for field, value in entry.iteritems():
            if field in unquote:
                value = urllib.unquote(value)
            if re.search(regexp, value, re.IGNORECASE|re.UNICODE):
                log.debug('match from %s' % field)
                return True

    def feed_filter(self, feed):
        """This method is overriden by ignore and accept modules"""
        self.filter(feed, feed.accept, feed.filter, 'patterns')

    def filter(self, feed, match_method, non_match_method, keyword):
        """
            match_method - passed method is called with a entry as a parameter when entry matches rule
            non_match_method - passed method is called with a entry as a parameter when entry does NOT match rule
            keyword - used to get rules from feed configuration
        """
        for entry in feed.entries:
            match = False
            for regexp_raw in feed.config.get(keyword, []):
                # set custom path for entry if pattern specifies one
                path = None
                secondary = []
                if isinstance(regexp_raw, dict):
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
                    # if we have secondary (filter) regexps test them
                    for secondary_re in secondary:
                        if self.matches(entry, secondary_re):
                            log.debug("%s: Secondary filter regexp '%s' matched '%s'" % (keyword, entry['title'], secondary_re))
                            match = False
                            
                if match:
                    if path: entry['path'] = path
                    log.debug("%s: '%s' matched '%s'" % (keyword, entry['title'], regexp_raw))
                    break
                    
            if match:
                if match_method:
                    match_method(entry)
            else:
                if non_match_method:
                    non_match_method(entry)           
