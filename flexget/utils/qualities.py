import copy
import functools
import re
from typing import Dict, Iterator, List, Optional, Set, Tuple, Union

from loguru import logger

from flexget.utils.serialization import Serializer

logger = logger.bind(name='utils.qualities')


@functools.total_ordering
class QualityComponent:
    """"""

    def __init__(
        self,
        type: str,
        value: int,
        name: str,
        regexp: Optional[str] = None,
        modifier: Optional[int] = None,
        defaults: Optional[List['QualityComponent']] = None,
    ) -> None:
        """
        :param type: Type of quality component. (resolution, source, codec, color_range or audio)
        :param value: Value used to sort this component with others of like type.
        :param name: Canonical name for this quality component.
        :param regexp: Regexps used to match this component.
        :param modifier: An integer that affects sorting above all other components.
        :param defaults: An iterable defining defaults for other quality components if this component matches.
        """

        if type not in ['resolution', 'source', 'codec', 'color_range', 'audio']:
            raise ValueError('%s is not a valid quality component type.' % type)
        self.type = type
        self.value = value
        self.name = name
        self.modifier = modifier
        self.defaults = defaults or []

        # compile regexp
        if regexp is None:
            regexp = re.escape(name)
        self.regexp = re.compile(r'(?<![^\W_])(' + regexp + r')(?![^\W_])', re.IGNORECASE)

    def matches(self, text: str) -> Tuple[bool, str]:
        """Test if quality matches to text.

        :param string text: data te be tested against
        :returns: tuple (matches, remaining text without quality data)
        """

        match = self.regexp.search(text)
        if not match:
            return False, ""
        else:
            # remove matching part from the text
            text = text[: match.start()] + text[match.end() :]
        return True, text

    def __hash__(self) -> int:
        return hash(self.type + str(self.value))

    def __bool__(self) -> bool:
        return bool(self.value)

    def __eq__(self, other) -> bool:
        if isinstance(other, str):
            other = _registry.get(other)
        if not isinstance(other, QualityComponent):
            raise TypeError('Cannot compare %r and %r' % (self, other))
        if other.type == self.type:
            return self.value == other.value
        else:
            raise TypeError('Cannot compare %s and %s' % (self.type, other.type))

    def __lt__(self, other) -> bool:
        if isinstance(other, str):
            other = _registry.get(other)
        if not isinstance(other, QualityComponent):
            raise TypeError('Cannot compare %r and %r' % (self, other))
        if other.type == self.type:
            return self.value < other.value
        else:
            raise TypeError('Cannot compare %s and %s' % (self.type, other.type))

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

    def __repr__(self) -> str:
        return f'<{self.type.title()}(name={self.name},value={self.value})>'

    def __str__(self) -> str:
        return self.name

    def __deepcopy__(self, memo=None):
        # No mutable attributes, return a regular copy
        return copy.copy(self)


_resolutions = [
    QualityComponent('resolution', 10, '360p'),
    QualityComponent('resolution', 20, '368p', '368p?'),
    QualityComponent('resolution', 30, '480p', '480p?'),
    QualityComponent('resolution', 35, '540p', '540p?'),
    QualityComponent('resolution', 40, '576p', '576p?'),
    QualityComponent('resolution', 45, 'hr'),
    QualityComponent('resolution', 50, '720i'),
    QualityComponent('resolution', 60, '720p', '(1280x)?720(p|hd)?x?([56]0)?'),
    QualityComponent('resolution', 70, '1080i'),
    QualityComponent('resolution', 80, '1080p', '(1920x)?1080p?x?([56]0)?'),
    QualityComponent('resolution', 90, '2160p', '((3840x)?2160p?x?([56]0)?)|4k'),
]
_sources = [
    QualityComponent('source', 10, 'workprint', modifier=-8),
    QualityComponent('source', 20, 'cam', '(?:hd)?cam', modifier=-7),
    QualityComponent('source', 30, 'ts', '(?:hd)?ts|telesync', modifier=-6),
    QualityComponent('source', 40, 'tc', 'tc|telecine', modifier=-5),
    QualityComponent('source', 50, 'r5', 'r[2-8c]', modifier=-4),
    QualityComponent('source', 60, 'hdrip', r'hd[\W_]?rip', modifier=-3),
    QualityComponent('source', 70, 'ppvrip', r'ppv[\W_]?rip', modifier=-2),
    QualityComponent('source', 80, 'preair', modifier=-1),
    QualityComponent('source', 90, 'tvrip', r'tv[\W_]?rip'),
    QualityComponent('source', 100, 'dsr', r'dsr|ds[\W_]?rip'),
    QualityComponent('source', 110, 'sdtv', r'(?:[sp]dtv|dvb)(?:[\W_]?rip)?'),
    QualityComponent('source', 120, 'dvdscr', r'(?:(?:dvd|web)[\W_]?)?scr(?:eener)?', modifier=0),
    QualityComponent('source', 130, 'bdscr', 'bdscr(?:eener)?'),
    QualityComponent('source', 140, 'webrip', r'web[\W_]?rip'),
    QualityComponent('source', 150, 'hdtv', r'a?hdtv(?:[\W_]?rip)?'),
    QualityComponent('source', 160, 'webdl', r'web(?:[\W_]?(dl|hd))?'),
    QualityComponent('source', 170, 'dvdrip', r'dvd(?:[\W_]?rip)?'),
    QualityComponent('source', 175, 'remux'),
    QualityComponent('source', 180, 'bluray', r'(?:b[dr][\W_]?rip|blu[\W_]?ray(?:[\W_]?rip)?)'),
]
_codecs = [
    QualityComponent('codec', 10, 'divx'),
    QualityComponent('codec', 20, 'xvid'),
    QualityComponent('codec', 30, 'h264', '[hx].?264'),
    QualityComponent('codec', 35, 'vp9'),
    QualityComponent('codec', 40, 'h265', '[hx].?265|hevc'),
]

_color_ranges = [
    QualityComponent('color_range', 10, '8bit', r'8[^\w]?bits?|hi8p?'),
    QualityComponent('color_range', 20, '10bit', r'10[^\w]?bits?|hi10p?'),
    QualityComponent('color_range', 40, 'hdrplus', r'hdr[^\w]?(\+|p|plus)'),
    QualityComponent('color_range', 30, 'hdr', r'hdr([^\w]?10)?'),
    QualityComponent('color_range', 50, 'dolbyvision', r'(dolby[^\w]?vision|dv|dovi)'),
]

channels = r'(?:(?:[^\w+]?[1-7][\W_]?(?:0|1|ch)))'
_audios = [
    QualityComponent('audio', 10, 'mp3'),
    # TODO: No idea what order these should go in or if we need different regexps
    QualityComponent('audio', 20, 'aac', 'aac%s?' % channels),
    QualityComponent('audio', 30, 'dd5.1', 'dd%s' % channels),
    QualityComponent('audio', 40, 'ac3', 'ac3%s?' % channels),
    QualityComponent('audio', 45, 'dd+5.1', 'dd[p+]%s' % channels),
    QualityComponent('audio', 50, 'flac', 'flac%s?' % channels),
    # The DTSs are a bit backwards, but the more specific one needs to be parsed first
    QualityComponent('audio', 70, 'dtshd', r'dts[\W_]?hd(?:[\W_]?ma)?%s?' % channels),
    QualityComponent('audio', 60, 'dts'),
    QualityComponent('audio', 80, 'truehd', 'truehd%s?' % channels),
]

_UNKNOWNS = {
    'resolution': QualityComponent('resolution', 0, 'unknown'),
    'source': QualityComponent('source', 0, 'unknown'),
    'codec': QualityComponent('codec', 0, 'unknown'),
    'color_range': QualityComponent('color_range', 0, 'unknown'),
    'audio': QualityComponent('audio', 0, 'unknown'),
}

# For wiki generating help
'''for type in (_resolutions, _sources, _codecs, _color_ranges, _audios):
    print '{{{#!td style="vertical-align: top"'
    for item in reversed(type):
        print '- ' + item.name
    print '}}}'
'''

_registry: Dict[Union[str, QualityComponent], QualityComponent] = {}
for items in (_resolutions, _sources, _codecs, _color_ranges, _audios):
    for item in items:
        _registry[item.name] = item


def all_components() -> Iterator[QualityComponent]:
    return iter(_registry.values())


@functools.total_ordering
class Quality(Serializer):
    """Parses and stores the quality of an entry in the four component categories."""

    def __init__(self, text: str = '') -> None:
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
            self.color_range = _UNKNOWNS['color_range']
            self.audio = _UNKNOWNS['audio']

    def parse(self, text: str) -> None:
        """Parses a string to determine the quality in the four component categories.

        :param text: The string to parse
        """
        self.text = text
        self.clean_text = text
        self.resolution = self._find_best(_resolutions, _UNKNOWNS['resolution'], False)
        self.source = self._find_best(_sources, _UNKNOWNS['source'])
        self.codec = self._find_best(_codecs, _UNKNOWNS['codec'])
        self.color_range = self._find_best(_color_ranges, _UNKNOWNS['color_range'])
        self.audio = self._find_best(_audios, _UNKNOWNS['audio'])
        # If any of the matched components have defaults, set them now.
        for component in self.components:
            for default in component.defaults:
                default = _registry[default]
                if not getattr(self, default.type):
                    setattr(self, default.type, default)

    def _find_best(
        self,
        qlist: List[QualityComponent],
        default: QualityComponent,
        strip_all: bool = True,
    ) -> QualityComponent:
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
    def name(self) -> str:
        name = ' '.join(
            str(p)
            for p in (self.resolution, self.source, self.codec, self.color_range, self.audio)
            if p.value != 0
        )
        return name or 'unknown'

    @property
    def components(self) -> List[QualityComponent]:
        return [self.resolution, self.source, self.codec, self.color_range, self.audio]

    @classmethod
    def serialize(cls, quality: 'Quality') -> str:
        return str(quality)

    @classmethod
    def deserialize(cls, data: str, version: int) -> 'Quality':
        return cls(data)

    @property
    def _comparator(self) -> List:
        modifier = sum(c.modifier for c in self.components if c.modifier)
        return [modifier] + self.components

    def __contains__(self, other):
        if isinstance(other, str):
            other = Quality(other)
        if not other or not self:
            return False
        for cat in ('resolution', 'source', 'audio', 'color_range', 'codec'):
            othercat = getattr(other, cat)
            if othercat and othercat != getattr(self, cat):
                return False
        return True

    def __bool__(self) -> bool:
        return any(self._comparator)

    def __eq__(self, other) -> bool:
        if isinstance(other, str):
            other = Quality(other)
        if not isinstance(other, Quality):
            if other is None:
                return False
            raise TypeError('Cannot compare %r and %r' % (self, other))
        return self._comparator == other._comparator

    def __lt__(self, other) -> bool:
        if isinstance(other, str):
            other = Quality(other)
        if not isinstance(other, Quality):
            raise TypeError('Cannot compare %r and %r' % (self, other))
        return self._comparator < other._comparator

    def __repr__(self) -> str:
        return '<Quality(resolution=%s,source=%s,codec=%s,color_range=%s,audio=%s)>' % (
            self.resolution,
            self.source,
            self.codec,
            self.color_range,
            self.audio,
        )

    def __str__(self) -> str:
        return self.name

    def __hash__(self) -> int:
        # Make these usable as dict keys
        return hash(self.name)


def get(quality_name: str) -> Quality:
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


class RequirementComponent:
    """Represents requirements for a given component type. Can evaluate whether a given QualityComponent
    meets those requirements."""

    def __init__(self, type: str) -> None:
        self.type = type
        self.min: Optional[QualityComponent] = None
        self.max: Optional[QualityComponent] = None
        self.acceptable: Set[QualityComponent] = set()
        self.none_of: Set[QualityComponent] = set()

    def reset(self) -> None:
        self.min = None
        self.max = None
        self.acceptable = set()
        self.none_of = set()

    def allows(self, comp: QualityComponent, loose: bool = False) -> bool:
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

    def add_requirement(self, text: str) -> None:
        if '-' in text:
            min_str, max_str = text.split('-')
            min_quality, max_quality = _registry[min_str], _registry[max_str]
            if min_quality.type != max_quality.type != self.type:
                raise ValueError('Component type mismatch: %s' % text)
            self.min, self.max = min_quality, max_quality
        elif '|' in text:
            req_quals = text.split('|')
            quals = {_registry[qual] for qual in req_quals}
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

    def __eq__(self, other) -> bool:
        if not isinstance(other, RequirementComponent):
            return False
        return (self.max, self.max, self.acceptable, self.none_of) == (
            other.max,
            other.max,
            other.acceptable,
            other.none_of,
        )

    def __hash__(self) -> int:
        return hash(
            tuple(
                [self.min, self.max, tuple(sorted(self.acceptable)), tuple(sorted(self.none_of))]
            )
        )


class Requirements:
    """Represents requirements for allowable qualities. Can determine whether a given Quality passes requirements."""

    def __init__(self, req: str = '') -> None:
        self.text = ''
        self.resolution = RequirementComponent('resolution')
        self.source = RequirementComponent('source')
        self.codec = RequirementComponent('codec')
        self.color_range = RequirementComponent('color_range')
        self.audio = RequirementComponent('audio')
        if req:
            self.parse_requirements(req)

    @property
    def components(self) -> List[RequirementComponent]:
        return [self.resolution, self.source, self.codec, self.color_range, self.audio]

    def parse_requirements(self, text: str) -> None:
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

    def allows(self, qual: Union[Quality, str], loose: bool = False) -> bool:
        """Determine whether this set of requirements allows a given quality.

        :param Quality qual: The quality to evaluate.
        :param bool loose: If True, only ! (not) requirements will be enforced.
        :rtype: bool
        :returns: True if given quality passes all component requirements.
        """
        if isinstance(qual, str):
            qual = Quality(qual)
        for r_component, q_component in zip(self.components, qual.components):
            if not r_component.allows(q_component, loose=loose):
                return False
        return True

    def __eq__(self, other) -> bool:
        if isinstance(other, str):
            other = Requirements(other)
        return self.components == other.components

    def __hash__(self) -> int:
        return hash(tuple(self.components))

    def __str__(self) -> str:
        return self.text or 'any'

    def __repr__(self) -> str:
        return f'<Requirements({self})>'
