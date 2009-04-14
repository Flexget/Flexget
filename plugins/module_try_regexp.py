import logging
import re

__pychecker__ = 'unusednames=parser'

log = logging.getLogger('try_regexp')

class PluginTryRegexp:

    """
        This plugin allows user to test regexps for a feed.
    """

    def register(self, manager, parser):
        manager.register('try_regexp', builtin=True)
        parser.add_option('--try', action='store_true', dest='try_regexp', default=False,
                          help='Try regular expressions interactively.')
        self.abort = False

    def validator(self):
        # this is not ment to be configured .. :)
        import validator
        return validator.factory('any')
        
    def matches(self, entry, regexp):
        """Return True if any of the entry string fields match given regexp"""
        for field, value in entry.iteritems():
            if not isinstance(value, basestring):
                continue
            if re.search(regexp, value, re.IGNORECASE|re.UNICODE):
                return (True, field)
        return (False, None)
        
    def feed_filter(self, feed):
        if not feed.manager.options.try_regexp and not 'try_regexp' in feed.config:
            return
        if self.abort: 
            return
        
        print '-'*79
        print 'Hi there, welcome to try regexps in realtime!'
        print 'Press ^D or type \'exit\' to continue. Type \'abort\' to continue non-interactive execution.'
        print 'Feed \'%s\' has %s entries, enter regexp to see what matches it.' % (feed.name, len(feed.entries))
        while (True):
            try:
                s = raw_input('--> ')
                if s=='exit': 
                    break
                if s=='abort':
                    self.abort = True
                    break
            except EOFError:
                break
            
            count = 0
            for entry in feed.entries:
                try:
                    match, field = self.matches(entry, s)
                    if match:
                        print 'Title: %-40s URL: %-30s From: %s' % (entry['title'], entry['url'], field)
                        count += 1
                except:
                    print 'Invalid regular expression'
                    break
            print '%s entries matched' % count
        print 'Bye!'       
