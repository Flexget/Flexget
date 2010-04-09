class Quality(object):

    def __init__(self, value, name):
        self.value = value
        self.name = name

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
        return '<Quality(name=%s,value=%s)>' % (self.name, self.value)
        
    __repr__ = __str__


class UnknownQuality(Quality):

    def __init__(self):
        self.value = 0
        self.name = 'unknown'


registry = {'1080p': Quality(1000, '1080p'),
            '1080': Quality(1000, '1080p'),
            '1920x1080': Quality(1000, '1080p'),
            '1080i': Quality(750, '1080i'),
            '720p': Quality(500, '720p'),
            '720': Quality(500, '720p'),
            '1280x720': Quality(500, '720p'),
            '720i': Quality(450, '720i'),
            'hr': Quality(400, 'hr'),
            'dvd': Quality(350, 'dvdrip'),
            'bdrip': Quality(350, 'dvdrip'),
            'dvdrip': Quality(350, 'dvdrip'),
            '480p': Quality(300, '480p'),
            '480': Quality(300, '480p'),
            'hdtv': Quality(290, 'hdtv'),
            'bdscr': Quality(280, 'bdscr'),
            'dvdscr': Quality(250, 'dvdscr'),
            'sdtv': Quality(100, 'sdtv'),
            'pdtv': Quality(100, 'sdtv'),
            'dsr': Quality(80, 'dsr'),
            'dsrip': Quality(80, 'dsr'),
            'r5': Quality(50, 'r5'),
            'tc': Quality(40, 'tc'),
            'preair': Quality(30, 'preair'),
            'cam': Quality(20, 'cam'),
            'workprint': Quality(10, 'workprint'),
            'unknown': UnknownQuality()}


def get(name):
    """Return Quality object for :name: (case insensitive)"""
    return registry.get(name.lower(), UnknownQuality())


def value(name):
    """Return value of quality with :name: (case insensitive) or 0 if unknown"""
    return registry.get(name.lower(), UnknownQuality()).value


def min():
    """Return lowest known Quality excluding unknown."""
    min = None
    for quality in registry.itervalues():
        if isinstance(quality, UnknownQuality):
            continue
        if min is None:
            min = quality
        if quality.value < min.value:
            min = quality
    return min

    
def max():
    """Return highest known Quality."""
    max = None
    for quality in registry.itervalues():
        if max is None:
            max = quality
        if quality.value > max.value:
            max = quality
    return max

    
def common_name(name):
    """Return `common name` for :name: (case insensitive)
    ie.
    names 1280x720, 720 and 720p will all return 720p"""
    return registry.get(name.lower(), UnknownQuality()).name
