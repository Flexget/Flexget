__instance__ = 'FilterPatterns'

import urllib
import logging
import re
import types

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
        manager.register(instance=self, type="filter", keyword="patterns", callback=self.patterns, order=-200)
        parser.add_option("--try-pattern", action="store", dest="try_pattern", default=None,
                          help="Run with given pattern. Usefull to try out matcing with --test.")

    def matches(self, entry, regexp):
        #TODO: match from all fields from entry?
        regexp = str(regexp)
        entry_url = urllib.unquote(entry['url'])
        if re.search(regexp, entry_url, re.IGNORECASE|re.UNICODE) or re.search(regexp, entry['title'], re.IGNORECASE|re.UNICODE):
            return True

    def patterns(self, feed):
        self.filter(feed, None, feed.filter, 'patterns')

    def filter(self, feed, match_method, non_match_method, keyword):
        for entry in feed.entries:
            match = False
            for regexp_raw in feed.config.get(keyword, []):
                # set custom path for entry if pattern specifies one
                path = None
                secondary = []
                if type(regexp_raw) == types.DictType:
                    regexp_raw, value = regexp_raw.items()[0]
                    # if regexp has dict as parameter
                    if type(value) == types.DictType:
                        path = value.get('path', None)
                        if value.has_key('not'):
                            if type(value['not'])==types.ListType: secondary.extend(value['not'])
                            else: secondary.append(value['not'])
                    else:
                        path = value

                # check if entry matches given regexp
                if self.matches(entry, regexp_raw):
                    match = True
                    # if we have secondary (filter) regexps test them
                    for secondary_re in secondary:
                        if self.matches(entry, secondary_re):
                            logging.debug("%s: Secondary filter regexp '%s' matched '%s'" % (keyword, entry['title'], secondary_re))
                            match = False
                            
                if match:
                    if path != None: entry['path'] = path
                    logging.debug("%s: '%s' matched '%s'" % (keyword, entry['title'], regexp_raw))
                    break
                    
            if match:
                if match_method != None:
                    match_method(entry)
            else:
                if non_match_method != None:
                    non_match_method(entry)
            
