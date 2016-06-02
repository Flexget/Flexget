from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from past.builtins import basestring

import re
import copy
import logging

log = logging.getLogger('utils.qualities')


class QualityComponent(object):
    """"""
    def __init__(self, type, value, name, regexp=None, modifier=None, defaults=None):
        """
        :param type: Type of quality component. (resolution, source, codec, or audio)
        :param value: Value used to sort this component with others of like type.
        :param name: Canonical name for this quality component.
        :param regexp: Regexps used to match this component.
        :param modifier: An integer that affects sorting above all other components.
        :param defaults: An iterable defining defaults for other quality components if this component matches.
        """

        if type not in ['resolution', 'source', 'codec', 'audio']:
            raise ValueError('%s is not a valid quality component type.' % type)
        self.type = type
        self.value = value
        self.name = name
        self.modifier = modifier
        self.defaults = defaults or []

        # compile regexp
        if regexp is None:
            regexp = re.escape(name)
        self.regexp = re.compile('(?<![^\W_])(' + regexp + ')(?![^\W_])', re.IGNORECASE)

    def matches(self, text):
        """Test if quality matches to text.

        :param string text: data te be tested against
        :returns: tuple (matches, remaining text without quality data)
        """

        match = self.regexp.search(text)
        if not match:
            return False, ""
        else:
            # remove matching part from the text
            text = text[:match.start()] + text[match.end():]
        return True, text

    def __hash__(self):
        return hash(self.type + str(self.value))

    def __bool__(self):
        return bool(self.value)

    def __eq__(self, other):
        if isinstance(other, basestring):
            other = _registry.get(other)
        if not isinstance(other, QualityComponent):
            raise TypeError('Cannot compare %r and %r' % (self, other))
        if other.type == self.type:
            return self.value == other.value
        else:
            raise TypeError('Cannot compare %s and %s' % (self.type, other.type))

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        if isinstance(other, basestring):
            other = _registry.get(other)
        if not isinstance(other, QualityComponent):
            raise TypeError('Cannot compare %r and %r' % (self, other))
        if other.type == self.type:
            return self.value < other.value
        else:
            raise TypeError('Cannot compare %s and %s' % (self.type, other.type))

    def __ge__(self, other):
        return not self.__lt__(other)

    def __le__(self, other):
        return self.__lt__(other) or self.__eq__(other)

    def __gt__(self, other):
        return not self.__le__(other)

    def __add__(self, other):
        if not isinstance(other, int):
            raise TypeError()
        l = globals().get('_' + self.type + 's')
        index = l.index(self) + other
        if index >= len(l):
            index = -1
        return l[index]

    def __sub__(self, other):
        if not isinstance(other, int):
            raise TypeError()
        l = globals().get('_' + self.type + 's')
        index = l.index(self) - other
        if index < 0:
            index = 0
        return l[index]

    def __repr__(self):
        return '<%s(name=%s,value=%s)>' % (self.type.title(), self.name, self.value)

    def __str__(self):
        return self.name

    def __deepcopy__(self, memo=None):
        # No mutable attributes, return a regular copy
        return copy.copy(self)

_resolutions = [
    QualityComponent('resolution', 10, '360p'),
    QualityComponent('resolution', 20, '368p', '368p?'),
    QualityComponent('resolution', 30, '480p', '480p?'),
    QualityComponent('resolution', 40, '576p', '576p?'),
    QualityComponent('resolution', 45, 'hr'),
    QualityComponent('resolution', 50, '720i'),
    QualityComponent('resolution', 60, '720p', '(1280x)?720(p|hd)?x?(50)?'),
    QualityComponent('resolution', 70, '1080i'),
    QualityComponent('resolution', 80, '1080p', '(1920x)?1080p?x?(50)?')
]
_sources = [
    QualityComponent('source', 10, 'workprint', modifier=-8),
    QualityComponent('source', 20, 'cam', '(?:hd)?cam', modifier=-7),
    QualityComponent('source', 30, 'ts', '(?:hd)?ts|telesync', modifier=-6),
    QualityComponent('source', 40, 'tc', 'tc|telecine', modifier=-5),
    QualityComponent('source', 50, 'r5', 'r[2-8c]', modifier=-4),
    QualityComponent('source', 60, 'hdrip', 'hd[\W_]?rip', modifier=-3),
    QualityComponent('source', 70, 'ppvrip', 'ppv[\W_]?rip', modifier=-2),
    QualityComponent('source', 80, 'preair', modifier=-1),
    QualityComponent('source', 90, 'tvrip', 'tv[\W_]?rip'),
    QualityComponent('source', 100, 'dsr', 'dsr|ds[\W_]?rip'),
    QualityComponent('source', 110, 'sdtv', '(?:[sp]dtv|dvb)(?:[\W_]?rip)?'),
    QualityComponent('source', 120, 'webrip', 'web[\W_]?rip'),
    QualityComponent('source', 130, 'dvdscr', '(?:(?:dvd|web)[\W_]?)?scr(?:eener)?', modifier=0),
    QualityComponent('source', 140, 'bdscr', 'bdscr(?:eener)?'),
    QualityComponent('source', 150, 'hdtv', 'a?hdtv(?:[\W_]?rip)?'),
    QualityComponent('source', 160, 'webdl', 'web(?:[\W_]?(dl|hd))'),
    QualityComponent('source', 170, 'dvdrip', 'dvd(?:[\W_]?rip)?'),
    QualityComponent('source', 175, 'remux'),
    QualityComponent('source', 180, 'bluray', '(?:b[dr][\W_]?rip|blu[\W_]?ray(?:[\W_]?rip)?)')
]
_codecs = [
    QualityComponent('codec', 10, 'divx'),
    QualityComponent('codec', 20, 'xvid'),
    QualityComponent('codec', 30, 'h264', '[hx].?264'),
    QualityComponent('codec', 40, 'h265', '[hx].?265|hevc'),
    QualityComponent('codec', 50, '10bit', '10.?bit|hi10p')
]
channels = '(?:(?:[\W_]?5[\W_]?1)|(?:[\W_]?2[\W_]?(?:0|ch)))'
_audios = [
    QualityComponent('audio', 10, 'mp3'),
    # TODO: No idea what order these should go in or if we need different regexps
    QualityComponent('audio', 20, 'aac', 'aac%s?' % channels),
    QualityComponent('audio', 30, 'dd5.1', 'dd%s' % channels),
    QualityComponent('audio', 40, 'ac3', 'ac3%s?' % channels),
    QualityComponent('audio', 50, 'flac', 'flac%s?' % channels),
    # The DTSs are a bit backwards, but the more specific one needs to be parsed first
    QualityComponent('audio', 60, 'dtshd', 'dts[\W_]?hd(?:[\W_]?ma)?'),
    QualityComponent('audio', 70, 'dts'),
    QualityComponent('audio', 80, 'truehd')
]

_UNKNOWNS = {
    'resolution': QualityComponent('resolution', 0, 'unknown'),
    'source': QualityComponent('source', 0, 'unknown'),
    'codec': QualityComponent('codec', 0, 'unknown'),
    'audio': QualityComponent('audio', 0, 'unknown')
}

# For wiki generating help
'''for type in (_resolutions, _sources, _codecs, _audios):
    print '{{{#!td style="vertical-align: top"'
    for item in reversed(type):
        print '- ' + item.name
    print '}}}'
'''


_registry = {}
for items in (_resolutions, _sources, _codecs, _audios):
    for item in items:
        _registry[item.name] = item


def all_components():
    return iter(_registry.values())


class Quality(object):
    """Parses and stores the quality of an entry in the four component categories."""

    def __init__(self, text=''):
        """
        :param text: A string to parse quality from
        """
        self.text = text
        self.clean_text = text
        if text:
            self.parse(text)
        else:
            self.resolution = _UNKNOWNS['resolution']
            self.source = _UNKNOWNS['source']
            self.codec = _UNKNOWNS['codec']
            self.audio = _UNKNOWNS['audio']

    def parse(self, text):
        """Parses a string to determine the quality in the four component categories.

        :param text: The string to parse
        """
        self.text = text
        self.clean_text = text
        self.resolution = self._find_best(_resolutions, _UNKNOWNS['resolution'], False)
        self.source = self._find_best(_sources, _UNKNOWNS['source'])
        self.codec = self._find_best(_codecs, _UNKNOWNS['codec'])
        self.audio = self._find_best(_audios, _UNKNOWNS['audio'])
        # If any of the matched components have defaults, set them now.
        for component in self.components:
            for default in component.defaults:
                default = _registry[default]
                if not getattr(self, default.type):
                    setattr(self, default.type, default)

    def _find_best(self, qlist, default=None, strip_all=True):
        """Finds the highest matching quality component from `qlist`"""
        result = None
        search_in = self.clean_text
        for item in qlist:
            match = item.matches(search_in)
            if match[0]:
                result = item
                self.clean_text = match[1]
                if strip_all:
                    # In some cases we want to strip all found quality components,
                    # even though we're going to return only the last of them.
                    search_in = self.clean_text
                if item.modifier is not None:
                    # If this item has a modifier, do not proceed to check higher qualities in the list
                    break
        return result or default

    @property
    def name(self):
        name = ' '.join(str(p) for p in (self.resolution, self.source, self.codec, self.audio) if p.value != 0)
        return name or 'unknown'

    @property
    def components(self):
        return [self.resolution, self.source, self.codec, self.audio]

    @property
    def _comparator(self):
        modifier = sum(c.modifier for c in self.components if c.modifier)
        return [modifier] + self.components

    def __contains__(self, other):
        if isinstance(other, basestring):
            other = Quality(other)
        if not other or not self:
            return False
        for cat in ('resolution', 'source', 'audio', 'codec'):
            othercat = getattr(other, cat)
            if othercat and othercat != getattr(self, cat):
                return False
        return True

    def __bool__(self):
        return any(self._comparator)

    def __eq__(self, other):
        if isinstance(other, basestring):
            other = Quality(other)
            if not other:
                raise TypeError('`%s` does not appear to be a valid quality string.' % other.text)
        if not isinstance(other, Quality):
            if other is None:
                return False
            raise TypeError('Cannot compare %r and %r' % (self, other))
        return self._comparator == other._comparator

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        if isinstance(other, basestring):
            other = Quality(other)
            if not other:
                raise TypeError('`%s` does not appear to be a valid quality string.' % other.text)
        if not isinstance(other, Quality):
            raise TypeError('Cannot compare %r and %r' % (self, other))
        return self._comparator < other._comparator

    def __ge__(self, other):
        return not self.__lt__(other)

    def __le__(self, other):
        return self.__lt__(other) or self.__eq__(other)

    def __gt__(self, other):
        return not self.__le__(other)

    def __repr__(self):
        return '<Quality(resolution=%s,source=%s,codec=%s,audio=%s)>' % (self.resolution, self.source,
                                                                         self.codec, self.audio)

    def __str__(self):
        return self.name

    def __hash__(self):
        # Make these usable as dict keys
        return hash(self.name)


def get(quality_name):
    """Returns a quality object based on canonical quality name."""

    found_components = {}
    for part in quality_name.lower().split():
        component = _registry.get(part)
        if not component:
            raise ValueError('`%s` is not a valid quality string' % part)
        if component.type in found_components:
            raise ValueError('`%s` cannot be defined twice in a quality' % component.type)
        found_components[component.type] = component
    if not found_components:
        raise ValueError('No quality specified')
    result = Quality()
    for type, component in found_components.items():
        setattr(result, type, component)
    return result


class RequirementComponent(object):
    """Represents requirements for a given component type. Can evaluate whether a given QualityComponent
    meets those requirements."""

    def __init__(self, type):
        self.type = type
        self.reset()

    def reset(self):
        self.min = None
        self.max = None
        self.acceptable = set()
        self.none_of = set()

    def allows(self, comp, loose=False):
        if comp.type != self.type:
            raise TypeError('Cannot compare %r against %s' % (comp, self.type))
        if comp in self.none_of:
            return False
        if loose:
            return True
        if comp in self.acceptable:
            return True
        if self.min or self.max:
            if self.min and comp < self.min:
                return False
            if self.max and comp > self.max:
                return False
            return True
        if not self.acceptable:
            return True
        return False

    def add_requirement(self, text):
        if '-' in text:
            min, max = text.split('-')
            min, max = _registry[min], _registry[max]
            if min.type != max.type != self.type:
                raise ValueError('Component type mismatch: %s' % text)
            self.min, self.max = min, max
        elif '|' in text:
            quals = text.split('|')
            quals = {_registry[qual] for qual in quals}
            if any(qual.type != self.type for qual in quals):
                raise ValueError('Component type mismatch: %s' % text)
            self.acceptable |= quals
        else:
            qual = _registry[text.strip('!<>=+')]
            if qual.type != self.type:
                raise ValueError('Component type mismatch!')
            if text in _registry:
                self.acceptable.add(qual)
            else:
                if text[0] == '<':
                    if text[1] != '=':
                        qual -= 1
                    self.max = qual
                elif text[0] == '>' or text.endswith('+'):
                    if text[1] != '=' and not text.endswith('+'):
                        qual += 1
                    self.min = qual
                elif text[0] == '!':
                    self.none_of.add(qual)

    def __eq__(self, other):
        return ((self.max, self.max, self.acceptable, self.none_of) ==
                (other.max, other.max, other.acceptable, other.none_of))

    def __hash__(self):
        return hash(tuple([self.min, self.max, tuple(sorted(self.acceptable)), tuple(sorted(self.none_of))]))


class Requirements(object):
    """Represents requirements for allowable qualities. Can determine whether a given Quality passes requirements."""
    def __init__(self, req=''):
        self.text = ''
        self.resolution = RequirementComponent('resolution')
        self.source = RequirementComponent('source')
        self.codec = RequirementComponent('codec')
        self.audio = RequirementComponent('audio')
        if req:
            self.parse_requirements(req)

    @property
    def components(self):
        return [self.resolution, self.source, self.codec, self.audio]

    def parse_requirements(self, text):
        """
        Parses a requirements string.

        :param text: The string containing quality requirements.
        """
        text = text.lower()
        if self.text:
            self.text += ' '
        self.text += text
        if self.text == 'any':
            for component in self.components:
                component.reset()
                return

        text = text.replace(',', ' ')
        parts = text.split()
        try:
            for part in parts:
                if '-' in part:
                    found = _registry[part.split('-')[0]]
                elif '|' in part:
                    found = _registry[part.split('|')[0]]
                else:
                    found = _registry[part.strip('!<>=+')]
                for component in self.components:
                    if found.type == component.type:
                        component.add_requirement(part)
        except KeyError as e:
            raise ValueError('%s is not a valid quality component.' % e.args[0])

    def allows(self, qual, loose=False):
        """Determine whether this set of requirements allows a given quality.

        :param Quality qual: The quality to evaluate.
        :param bool loose: If True, only ! (not) requirements will be enforced.
        :rtype: bool
        :returns: True if given quality passes all component requirements.
        """
        if isinstance(qual, basestring):
            qual = Quality(qual)
            if not qual:
                raise TypeError('`%s` does not appear to be a valid quality string.' % qual.text)
        for r_component, q_component in zip(self.components, qual.components):
            if not r_component.allows(q_component, loose=loose):
                return False
        return True

    def __eq__(self, other):
        if isinstance(other, str):
            other = Requirements(other)
        return self.components == other.components

    def __hash__(self):
        return hash(tuple(self.components))

    def __str__(self):
        return self.text or 'any'

    def __repr__(self):
        return '<Requirements(%s)>' % self
