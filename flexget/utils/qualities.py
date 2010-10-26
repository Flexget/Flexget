class Quality(object):

    def __init__(self, value, name, regexp=None):
        self.value = value
        self.name = name
        if not regexp:
            regexp = name
        self.regexp = regexp

    def __eq__(self, other):
        return self.value == other.value

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        return self.value < other.value

    def __le__(self, other):
        return self.value <= other.value

    def __gt__(self, other):
        return self.value > other.value

    def __ge__(self, other):
        return self.value >= other.value

    def __str__(self):
        return '<Quality(name=%s,value=%s,regexp=%s)>' % (self.name, self.value, self.regexp)

    __repr__ = __str__


class UnknownQuality(Quality):

    def __init__(self):
        self.value = 0
        self.name = 'unknown'
        self.regexp = None

qualities = [Quality(1000, '1080p', '(?:1920x)?1080p?'),
            Quality(750, '1080i'),
            Quality(600, 'web-dl'),
            Quality(500, '720p', '(?:1280x)?720p?'),
            Quality(450, '720i'),
            Quality(400, 'hr'),
            Quality(380, 'bdrip', 'b(?:[dr]rip|luray)'),
            Quality(350, 'dvdrip', 'dvd(?:rip)?'),
            Quality(300, '480p', '480p?'),
            Quality(290, 'hdtv', 'hdtv(?:[\W_]?rip)?'),
            Quality(280, 'bdscr'),
            Quality(250, 'dvdscr'),
            Quality(100, 'sdtv', '(?:[sp]dtv|dvb)(?:[\W_]?rip)?'),
            Quality(80, 'dsr', 'ds(?:r|[\W_]?rip)'),
            Quality(50, 'r5'),
            Quality(40, 'tc'),
            Quality(30, 'preair'),
            Quality(20, 'cam'),
            Quality(10, 'workprint')]

registry = dict([(qual.name.lower(), qual) for qual in qualities])
registry['unknown'] = UnknownQuality()


def all():
    """Return all Qualities in order of best to worst"""
    return sorted(qualities, reverse=True)


def get(name, *args):
    """Return Quality object for :name: (case insensitive)"""
    name = name.lower()
    if name in registry:
        return registry[name]
    q = parse_quality(name, True)
    if q.value:
        return q
    return args[0] if args else UnknownQuality()


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


def parse_quality(title, exact=False):
    """Find the highest know quality in a given string"""
    import re
    qualities.sort(reverse=True)
    # If exact mode make sure quality identifier is the entire string.
    # Otherwise make sure it is surrounded by non word characters.
    (lcap, rcap) = (r'\A', r'\Z') if exact else (r'([\W_]|\A)', r'([\W_]|\Z)')

    for qual in qualities:
        regexp = lcap + qual.regexp + rcap
        if re.search(regexp, title, re.IGNORECASE):
            return qual
    return UnknownQuality()
