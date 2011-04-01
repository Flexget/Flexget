import re
import copy
import logging

log = logging.getLogger('utils.qualities')


class Quality(object):

    def __init__(self, value, name, all_of=None, none_of=None):
        """
        Args:

            value: numerical value for quality, used for determining order
            name: commonly used name for the quality
            all_of: list of match_all that all need to match when testing
                    whether or not given text matches this quality
            none_of: list of match_all that cannot match to this quality
        """
        self.value = value
        self.name = name
        if not all_of:
            all_of = [name]
        self.regexps = []
        self.not_regexps = []

        # compile regexps
        for r in all_of:
            self.regexps.append(re.compile('(?<![^\W_])' + r + '(?![^\W_])', re.IGNORECASE))
        if none_of:
            for r in none_of:
                self.not_regexps.append(re.compile('(?<![^\W_])' + r + '(?![^\W_])', re.IGNORECASE))

    def matches(self, text):
        """Test if quality matches to text.
        
        Args:
        
            text: data te be tested against
            
        Returns:
            0 - True if matches
            1 - Remaining text, quality data stripped
        """
        #log.debug('testing for quality %s --->' % self.name)
        # none of these regexps can match
        for regexp in self.not_regexps:
            match = regexp.search(text)
            if match:
                #log.debug('`%s` matches to `%s`, cannot be `%s`' % (regexp.pattern, text, self.name))
                return False, ""
            #log.debug('`%s` missed `%s`' % (regexp.pattern, text))
        # all of the regexps must match
        for regexp in self.regexps:
            match = regexp.search(text)
            if not match:
                #log.debug('`%s` did not match to `%s`, cannot be `%s`' % (regexp.pattern, text, self.name))
                return False, ""
            else:
                # remove matching part from the text
                text = text[:match.start()] + text[match.end():]
            #log.debug('passed: ' + regexp.pattern)
        #log.debug('`%s` seems to be `%s`' % (text, self.name))
        return True, text

    def __hash__(self):
        return self.value

    def __eq__(self, other):
        if isinstance(other, basestring):
            other = get(other, None)
        if hasattr(other, 'value'):
            return self.value == other.value
        else:
            return NotImplemented

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        if isinstance(other, basestring):
            other = get(other, other)
        if not hasattr(other, 'value'):
            raise TypeError('%r is not a valid quality' % other)
        return self.value < other.value

    def __ge__(self, other):
        return not self.__lt__(other)

    def __le__(self, other):
        return self.__lt__(other) or self.__eq__(other)

    def __gt__(self, other):
        return not self.__le__(other)

    def __repr__(self):
        return '<Quality(name=%s,value=%s)>' % (self.name, self.value)

    def __str__(self):
        return self.name

    def __deepcopy__(self, memo={}):
        # No mutable attributes, return a regular copy
        return copy.copy(self)

UNKNOWN = Quality(0, 'unknown')

# Reminder, Quality regexps are automatically surrounded!
re_rc_or_r5 = 'rc|r5'
re_webdl = 'web[\W_]?dl'
re_720p = '(?:1280x)?720p?'
re_1080p = '(?:1920x)?1080p?'
re_bluray = '(?:b[dr][\W_]?rip|bluray(?:[\W_]?rip)?)'

qualities = [Quality(1100, '1080p bluray', [re_1080p, re_bluray], none_of=[re_rc_or_r5]),
             Quality(1000, '1080p web-dl', [re_1080p, re_webdl]),
             Quality(800, '1080p', [re_1080p], none_of=[re_bluray, re_rc_or_r5]),
             Quality(750, '1080i'),
             Quality(650, '720p bluray', [re_720p, re_bluray], none_of=[re_rc_or_r5]),
             Quality(600, '720p web-dl', [re_720p, re_webdl]),
             Quality(500, '720p', [re_720p], none_of=[re_bluray, re_rc_or_r5]),
             Quality(450, '720i'),
             Quality(430, '1080p bluray rc', [re_1080p, re_bluray, re_rc_or_r5]),
             Quality(420, '720p bluray rc', [re_720p, re_bluray, re_rc_or_r5]),
             Quality(400, 'hr'),
             Quality(380, 'bdrip', [re_bluray], none_of=[re_rc_or_r5]),
             Quality(350, 'dvdrip', ['dvd(?:[\W_]?rip)?'], none_of=[re_rc_or_r5]),
             Quality(320, 'web-dl', [re_webdl]),
             Quality(300, '480p', ['480p?']),
             Quality(290, 'hdtv', ['hdtv(?:[\W_]?rip)?']),
             Quality(285, 'dvdrip r5', ['dvd(?:[\W_]?rip)?', re_rc_or_r5]),
             Quality(280, 'bdscr'),
             Quality(250, 'dvdscr'),
             Quality(100, 'sdtv', ['(?:[sp]dtv|dvb)(?:[\W_]?rip)?|(?:t|pp)v[\W_]?rip']),
             Quality(80, 'dsr', ['ds(?:r|[\W_]?rip)']),
             Quality(50, 'r5'),
             Quality(40, 'tc'),
             Quality(30, 'preair'),
             Quality(20, 'cam'),
             Quality(10, 'workprint')]

registry = dict([(qual.name.lower(), qual) for qual in qualities])
registry['unknown'] = UNKNOWN


def all():
    """Return all Qualities in order of best to worst"""
    return sorted(qualities, reverse=True) + [UNKNOWN]


def get(name, *args):
    """Return Quality object for :name: (case insensitive)"""
    name = name.lower()
    if name in registry:
        return registry[name]
    q = parse_quality(name)
    if q.value:
        return q
    return args[0] if args else UNKNOWN


def value(name):
    """Return value of quality with :name: (case insensitive) or 0 if unknown"""
    return get(name).value


def min():
    """Return lowest known Quality excluding unknown."""
    qualities.sort()
    return qualities[0]


def max():
    """Return highest known Quality."""
    qualities.sort(reverse=True)
    return qualities[0]


def common_name(name):
    """Return `common name` for :name: (case insensitive)
    ie.
    names 1280x720, 720 and 720p will all return 720p"""
    return get(name).name


def quality_match(title):
    """Search best quality from title

    Args:
        title: text to search from

    Returns:
        0 - quality object matching or Unknown quality
        1 - remaining title, quality data removed
    """
    qualities.sort(reverse=True)
    for quality in qualities:
        result, remaining = quality.matches(title)
        if result:
            return quality, remaining
    return UNKNOWN, title


def parse_quality(title):
    """Find the highest know quality in a given string :title:
    
    Returns:
        quality object or False
    """
    return quality_match(title)[0]
