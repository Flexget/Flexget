import re
import copy
import logging
import __builtin__

log = logging.getLogger('utils.qualities')


class Quality(object):

    def __init__(self, value, name, all_of=None, blocker=False):
        """
        :param int value:
          numerical value for quality, used for determining order
        :param string name:
          commonly used name for the quality
        :param list all_of:
          list of regexps that all need to match when testing
          whether or not given text matches this quality
        :param bool blocker:
          if a blocker quality matches, parser will not try to find a higher quality
        """
        self.value = value
        self.name = name
        if not all_of:
            all_of = [name]
        self.regexps = []
        self.not_regexps = []
        self.blocker = blocker

        # compile regexps
        for r in all_of:
            self.regexps.append(re.compile('(?<![^\W_])' + r + '(?![^\W_])', re.IGNORECASE))

    def matches(self, text):
        """Test if quality matches to text.

        :param string text: data te be tested against
        :returns: tuple (matches, remaining text without quality data)
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

    def __deepcopy__(self, memo=None):
        # No mutable attributes, return a regular copy
        return copy.copy(self)

UNKNOWN = Quality(0, 'unknown')

# Reminder, Quality regexps are automatically surrounded!
re_region = 'r[3-8c]'
re_hdtv = 'hdtv(?:[\W_]?rip)?'
re_webdl = 'web[\W_]?dl'
re_720p = '(?:1280x)?720p?'
re_1080p = '(?:1920x)?1080p?'
re_bluray = '(?:b[dr][\W_]?rip|bluray(?:[\W_]?rip)?)'
re_10bit = '(10.?bit|hi10p)'

# TODO: this should be marked as private (_qualities), not sure if it used from other places though

qualities = [Quality(10, 'workprint', blocker=True),
             Quality(20, 'cam', blocker=True),
             Quality(25, 'ts', ['ts|telesync'], blocker=True),
             Quality(30, 'preair', blocker=True),
             Quality(40, 'tc', ['tc|telecine'], blocker=True),
             Quality(80, 'dsr', ['dsr|(?:ds|web)[\W_]?rip']),
             Quality(100, 'sdtv', ['(?:[sp]dtv|dvb)(?:[\W_]?rip)?|(?:t|pp)v[\W_]?rip']),
             Quality(240, 'dvdscr', ['(?:(?:dvd|web)[\W_]?)?scr(?:eener)?']),
             Quality(250, 'bdscr', ['bdscr(?:eener)?']),
             Quality(260, 'dvdrip r5', ['dvd(?:[\W_]?rip)?', re_region], blocker=True),
             Quality(270, 'hdtv', [re_hdtv]),
             Quality(280, '360p'), # I don't think we want to make trailing p optional here (ie. xbox 360)
             Quality(290, '368p', ['368p?']),
             Quality(300, '480p', ['480p?']),
             Quality(310, '480p 10bit', ['480p?', re_10bit], blocker=True),
             Quality(315, '576p', ['576p?']),
             Quality(320, 'web-dl', [re_webdl]),
             Quality(350, 'dvdrip', ['dvd(?:[\W_]?rip)?']),
             Quality(380, 'bdrip', [re_bluray]),
             Quality(400, 'hr'),
             Quality(420, '720p bluray rc', [re_720p, re_bluray, re_region], blocker=True),
             Quality(430, '1080p bluray rc', [re_1080p, re_bluray, re_region], blocker=True),
             # This is placed out of order to allow other r5 and rc matches to occur first
             Quality(50, 'r5', [re_region], blocker=True),
             Quality(450, '720i'),
             Quality(500, '720p', [re_720p]),
             Quality(520, '720p 10bit', [re_720p, re_10bit]),
             Quality(600, '720p web-dl', [re_720p, re_webdl]),
             Quality(650, '720p bluray', [re_720p, re_bluray]),
             Quality(670, '720p bluray 10bit', [re_720p, re_bluray, re_10bit], blocker=True),
             Quality(750, '1080i'),
             Quality(800, '1080p', [re_1080p]),
             Quality(850, '1080p 10bit', [re_1080p, re_10bit]),
             Quality(1000, '1080p web-dl', [re_1080p, re_webdl]),
             Quality(1100, '1080p bluray', [re_1080p, re_bluray]),
             Quality(1200, '1080p bluray 10bit', [re_1080p, re_bluray, re_10bit], blocker=True)]

registry = dict([(qual.name, qual) for qual in qualities])
registry['unknown'] = UNKNOWN


def all():
    """Return all Qualities in order of best to worst"""
    return qualities + [UNKNOWN]


def get(name, default=None):
    """
    Return Quality object for :name: (case insensitive)
    :param name: Quality name
    :return: Found :class:`Quality` / UNKNOWN or *default* if given and nothing was found.
    """
    name = name.lower()
    if name in registry:
        return registry[name]
    q = parse_quality(name)
    if q.value:
        return q
    return default if default is not None else UNKNOWN


def value(name):
    """
    :param str name: case insensitive quality name
    :return: Return value of quality with given *name* or 0 if unknown
    """
    return get(name).value


def min():
    """Return lowest known Quality excluding unknown."""
    return __builtin__.min(qualities)


def max():
    """Return highest known Quality."""
    return __builtin__.max(qualities)


def common_name(name):
    """Return `common name` for *name* (case insensitive).

    :param string name: Name to be converted in the common form.
    :returns: common name, eg. 1280x720, 720 and 720p will all return 720p
    :rtype: string
    """
    return get(name).name


def quality_match(title):
    """Search best quality from title

    :param string title: text to search from
    :returns: tuple (:class:`Quality` which can be unknown, remaining title without quality)
    """
    match = None
    for quality in qualities:
        result, remaining = quality.matches(title)
        if result:
            match = (quality, remaining)
            if quality.blocker:
                break
    if match:
        return match
    else:
        return UNKNOWN, title


def parse_quality(title):
    """Find the highest know quality in a given string :title:

    :returns: :class:`Quality` object or False
    """
    return quality_match(title)[0]
