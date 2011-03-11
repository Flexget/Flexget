class Quality(object):

    def __init__(self, value, name, regexp=None):
        import re
        self.value = value
        self.name = name
        if not regexp:
            regexp = name
        # Make sure regexp is surrounded by non word characters.
        self.regexp = re.compile('(?<![^\W_])' + regexp + '(?![^\W_])', re.IGNORECASE)

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

UNKNOWN = Quality(0, 'unknown')

re_webdl = 'web[\W_]?dl'
re_720p = '(?:1280x)?720p?'
re_1080p = '(?:1920x)?1080p?'
# Helper to return a re that matches the webdl re before or after ::x::
webdl_hybrid = lambda x: '(?P<webdl>' + re_webdl + '.*)?' + x + '(?(webdl)|.*' + re_webdl + ')'

qualities = [Quality(1000, '1080p web-dl', webdl_hybrid(re_1080p)),
            Quality(800, '1080p', re_1080p),
            Quality(750, '1080i'),
            Quality(600, '720p web-dl', webdl_hybrid(re_720p)),
            Quality(500, '720p', re_720p),
            Quality(450, '720i'),
            Quality(400, 'hr'),
            Quality(380, 'bdrip', '(?:b[dr][\W_]?rip)|(?:bluray(?:[\W_]?rip)?)'),
            Quality(350, 'dvdrip', 'dvd(?:[\W_]?rip)?'),
            Quality(320, 'web-dl', re_webdl),
            Quality(300, '480p', '480p?'),
            Quality(290, 'hdtv', 'hdtv(?:[\W_]?rip)?'),
            Quality(280, 'bdscr'),
            Quality(250, 'dvdscr'),
            Quality(100, 'sdtv', '(?:[sp]dtv|dvb)(?:[\W_]?rip)?|(?:t|pp)v[\W_]?rip'),
            Quality(80, 'dsr', 'ds(?:r|[\W_]?rip)'),
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
    q = parse_quality(name, True)
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


def quality_match(title, exact=False):
    qualities.sort(reverse=True)
    for qual in qualities:
        match = qual.regexp.search(title)
        if match:
            # If exact mode make sure quality identifier is the entire string.
            if not exact or match.span(0) == (0, len(title)):
                return qual, match
    return UNKNOWN, None


def parse_quality(title, exact=False):
    """Find the highest know quality in a given string"""
    return quality_match(title, exact)[0]
