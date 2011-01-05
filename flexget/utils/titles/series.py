import logging
import re
from flexget.utils.titles.parser import TitleParser, ParseWarning
from flexget.utils import qualities
from flexget.utils.tools import ReList

log = logging.getLogger('seriesparser')

# Forced to INFO !
# switch to logging.DEBUG if you want to debug this class (produces quite a bit info ..)
log.setLevel(logging.INFO)


class SeriesParser(TitleParser):

    """

    Parse series.

    :name: series name
    :data: data to parse
    :expect_ep: expect series to be in season, ep format (ep_regexps)
    :expect_id: expect series to be in id format (id_regexps)

    """
    separators = '[!/+,:;|~ x-]'
    roman_numeral_re = 'X{0,3}(?:IX|XI{0,4}|VI{0,4}|IV|V|I{1,4})'

    ep_regexps = ReList([TitleParser.re_not_in_word(regexp) for regexp in [
        '(?:series|season|s)\s?(\d{1,3})(?:\s(?:.*?\s)?)?(?:episode|ep|e|part|pt)\s?(\d{1,3}|%s)' % roman_numeral_re,
        '(?:series|season)\s?(\d{1,3})\s(\d{1,3})\s?of\s?(?:\d{1,3})',
        '(\d{1,3})\s?of\s?(?:\d{1,3})',
        '(\d{1,2})\s?x\s?(\d+)',
        '(?:episode|ep|part|pt)\s?(\d{1,3}|%s)' % roman_numeral_re]])
    unwanted_ep_regexps = ReList([
         '(\d{1,3})\s?x\s?(0+)[^1-9]', # 5x0
         'S(\d{1,3})D(\d{1,3})', # S3D1
         '(\d{1,3})\s?x\s?(all)', # 1xAll
         'season(?:s)?\s?\d\s?(?:&\s?\d)?[\s-]*(?:complete|full)',
         'seasons\s(\d\s){2,}',
         'disc\s\d',
         's\d+.?e\d+-\d+']) # S6 E1-4
    id_regexps = ReList([
        '(\d{4})%s(\d+)%s(\d+)' % (separators, separators),
        '(\d+)%s(\d+)%s(\d{4})' % (separators, separators),
        '(\d{4})x(\d+)\.(\d+)', '(pt|part)\s?(\d+|%s)' % roman_numeral_re,
        '(?:^|[^s\d])(\d{1,3})(?:[^p\d]|$)'])
    unwanted_id_regexps = ReList([
        'seasons?\s?\d{1,2}'])
    clean_regexps = ReList(['\[.*?\]', '\(.*?\)'])
    # ignore prefix regexpes must be passive groups with 0 or 1 occurrences  eg. (?:prefix)?
    ignore_prefixes = [
            '(?:\[[^\[\]]*\])', # ignores group names before the name, eg [foobar] name
            '(?:HD.720p?:)',
            '(?:HD.1080p?:)']

    def __init__(self, name='', identified_by='auto', name_regexps=None, ep_regexps=None, id_regexps=None,
                 strict_name=False, allow_groups=None):
        """Init SeriesParser.

        :name: Name of the series parser is going to try to parse.

        :identified_by: What kind of episode numbering scheme is expected, valid values are ep, id and auto (default).
        :name_regexps: List of regexps for name matching or None (default), by default regexp is generated from name.
        :ep_regexp: List of regexps detecting episode,season format. Given list is prioritized over built-in regexps.
        :id_regexp: List of regexps detecting id format. Given list is prioritized over built in regexps.
        :strict_name: Boolean value, if True name must be immediately be followed by episode identifier.
        :allow_groups: List of release group names that are allowed. This will also populate attribute `group`.
        """

        self.name = name
        self.data = ''
        self.expect_ep = identified_by == 'ep'
        self.expect_id = identified_by == 'id'
        self.name_regexps = ReList(name_regexps or [])
        self.re_from_name = False
        if ep_regexps:
            self.ep_regexps = ReList(ep_regexps + SeriesParser.ep_regexps)
            self.id_regexps = []
        elif id_regexps:
            self.id_regexps = ReList(id_regexps + SeriesParser.id_regexps)
            self.ep_regexps = []
        self.strict_name = strict_name
        self.allow_groups = allow_groups or []

        self.field = None
        self._reset()

    def _reset(self):
        # parse produces these
        self.season = None
        self.episode = None
        self.id = None
        self.id_groups = None
        self.quality = 'unknown'
        self.proper_or_repack = False
        self.special = False
        # TODO: group is only produced with allow_groups
        self.group = None

        # false if item does not match series
        self.valid = False

    def __setattr__(self, name, value):
        """
        Some conversions when setting attributes.
        `self.name` and `self.data` are converted to unicode.
        `self.*_regexps` are converted to ReList.
        """
        if name == 'name' or name == 'data':
            if isinstance(value, str):
                value = unicode(value)
            elif not isinstance(value, unicode):
                raise Exception('%s cannot be %s' % (name, repr(value)))
        elif name.endswith('_regexps'):
            # Transparently turn regular lists into ReLists
            value = ReList(value)
        object.__setattr__(self, name, value)

    def clean(self, data):
        """Perform data cleaner regexps."""
        # TODO: This method is no longer used, should it be removed?
        for clean_re in self.clean_regexps:
            matches = re.findall(clean_re, data)
            # remove all matches from data, unless they happen to contain relevant information
            if matches:
                for match in matches:
                    log.log(5, 'match: %s' % match)
                    safe = True
                    # Qualities can be safely removed, because they are detected from raw data
                    for proper in self.propers:
                        if proper.lower() in match.lower():
                            safe = False
                            break
                    if self.parse_episode(match):
                        log.log(5, '%s looks like a valid episode identifier' % match)
                        safe = False
                        break
                    if not safe:
                        break
                    else:
                        data = data.replace(match, '').strip()
        log.log(5, 'cleaned data: %s' % data)
        return data

    def remove_dirt(self, data):
        """Replaces some characters with spaces"""
        return re.sub(r'[_.,\[\]\(\): ]+', ' ', data).strip().lower()

    def parse(self, data=None, field=None, quality=None):
        # Clear the output variables before parsing
        self._reset()
        self.field = field
        self.quality = quality
        if data:
            self.data = data
        if not self.name or not self.data:
            raise Exception('SeriesParser initialization error, name: %s data: %s' % \
               (repr(self.name), repr(self.data)))

        if self.expect_ep and self.expect_id:
            raise Exception('Flags expect_ep and expect_id are mutually exclusive')

        name = self.remove_dirt(self.name)

        # check if data appears to be unwanted (abort)
        if self.parse_unwanted(self.remove_dirt(self.data)):
            return

        def name_to_re(name):
            """Convert 'foo bar' to '^[^...]*foo[^...]*bar[^...]+"""
            # TODO: Still doesn't handle the case where the user wants
            # "Schmost" and the feed contains "Schmost at Sea".
            blank = r'[\W_]'
            ignore = '(?:' + '|'.join(self.ignore_prefixes) + ')?'
            res = re.sub(blank + '+', ' ', name)
            res = res.strip()
            res = re.sub(' +', blank + '*', res)
            res = '^' + ignore + blank + '*' + '(' + res + ')' + blank + '+'
            return res

        log.debug('name: %s data: %s' % (name, self.data))

        # name end position
        name_start = 0
        name_end = 0

        # regexp name matching
        if not self.name_regexps:
            # if we don't have name_regexps, generate one from the name
            self.name_regexps = [name_to_re(name)]
            self.re_from_name = True
            if '&' in name:
                # if & is in the name, also add a regexp that accepts 'and' instead
                self.name_regexps.append(name_to_re(name.replace('&', 'and')))
        # try all specified regexps on this data
        for name_re in self.name_regexps:
            match = re.search(name_re, self.data)
            if match:
                if self.re_from_name:
                    name_start, name_end = match.span(1)
                else:
                    name_start, name_end = match.span()

                log.debug('NAME SUCCESS: %s matched to %s' % (name_re.pattern, self.data))
                break
        else:
            # leave this invalid
            log.debug('FAIL: name regexps %s do not match %s' % ([regexp.pattern for regexp in self.name_regexps],
                                                                 self.data))
            return


        # remove series name from raw data, move any prefix to end of string
        data_stripped = self.data[name_end:] + ' ' + self.data[:name_start]
        data_stripped = data_stripped.lower()
        log.debug('data stripped: %s' % data_stripped)

        # allow group(s)
        if self.allow_groups:
            for group in self.allow_groups:
                group = group.lower()
                for fmt in ['[%s]', '-%s']:
                    if fmt % group in data_stripped:
                        log.debug('%s is from group %s' % (self.data, group))
                        self.group = group
                        data_stripped = data_stripped.replace(fmt % group, '')
                        break
                if self.group:
                    break
            else:
                log.debug('%s is not from groups %s' % (self.data, self.allow_groups))
                return # leave invalid

        # search tags and quality if one was not provided to parse method
        if not quality or quality == 'unknown':
            log.debug('parsing quality ->')
            quality, match = qualities.quality_match(data_stripped)
            self.quality = quality.name
            if match:
                # Remove quality string from data
                data_stripped = data_stripped[:match.start()] + data_stripped[match.end():]

        # Remove unwanted words (qualities and such) from data for ep / id parsing
        data_stripped = self.remove_words(data_stripped, self.remove + qualities.registry.keys() +\
                                                         self.codecs + self.sounds, not_in_word=True)
        data_stripped = self.remove_dirt(data_stripped)

        data_parts = re.split('\W+', data_stripped)

        for part in data_parts:
            if part in self.propers:
                self.proper_or_repack = True
                data_parts.remove(part)
            if part in self.specials:
                self.special = True

        data_stripped = ' '.join(data_parts).strip()

        log.debug("data for id/ep parsing '%s'" % data_stripped)

        ep_match = self.parse_episode(data_stripped)
        if ep_match:
            # strict_name
            if self.strict_name:
                if ep_match[2].start() > 1:
                    return

            if self.expect_id:
                log.debug('found episode number, but expecting id, aborting!')
                return

            self.season = ep_match[0]
            self.episode = ep_match[1]
            self.valid = True
            return

        log.debug('-> no luck with ep_regexps')

        # search for ids later as last since they contain somewhat broad matches

        if self.expect_ep:
            # we should be getting season, ep !
            # try to look up idiotic numbering scheme 101,102,103,201,202
            # ressu: Added matching for 0101, 0102... It will fail on
            #        season 11 though
            log.debug('expect_ep enabled')
            match = re.search('(?:^|\D)(0?\d)(\d\d)\D', data_stripped, re.IGNORECASE | re.UNICODE)
            if match:
                # strict_name
                if self.strict_name:
                    if match.start() > 1:
                        return

                self.season = int(match.group(1))
                self.episode = int(match.group(2))
                log.debug(self)
                self.valid = True
                return
            log.debug('-> no luck with the expect_ep')
        else:
            if self.parse_unwanted_id(data_stripped):
                return
            for id_re in self.id_regexps:
                match = re.search(id_re, data_stripped)
                if match:
                    # strict_name
                    if self.strict_name:
                        if match.start() - name_end >= 2:
                            return

                    self.id = '-'.join(match.groups())
                    self.id_groups = match.groups()
                    if self.special:
                        self.id += '-SPECIAL'
                    self.valid = True
                    log.debug('found id \'%s\' with regexp \'%s\'' % (self.id, id_re))
                    return
            log.debug('-> no luck with id_regexps')

        # No id found, check if this is a special
        if self.special:
            # Attempt to set id as the title of the special
            self.id = data_stripped
            self.valid = True
            log.debug('found special, setting id to \'%s\'' % self.id)
            return

        raise ParseWarning('Title \'%s\' looks like series \'%s\' but I cannot find any episode or id numbering' % (self.data, self.name))

    def parse_unwanted(self, data):
        """Parses data for an unwanted hits. Return True if the data contains unwanted hits."""
        for ep_unwanted_re in self.unwanted_ep_regexps:
            match = re.search(ep_unwanted_re, data)
            if match:
                log.debug('unwanted regexp %s matched %s' % (ep_unwanted_re, match.groups()))
                return True

    def parse_unwanted_id(self, data):
        """Parses data for an unwanted id hits. Return True if the data contains unwanted hits."""
        for id_unwanted_re in self.unwanted_id_regexps:
            match = re.search(id_unwanted_re, data)
            if match:
                log.debug('unwanted id regexp %s matched %s' % (id_unwanted_re, match.groups()))
                return True

    def parse_episode(self, data):
        """
        Parses :data: for an episode identifier.
        If found, returns a tuple of season#, episode# and the regexp match object
        If no episode id is found returns False
        """

        # search for season and episode number
        for ep_re in self.ep_regexps:
            match = re.search(ep_re, data)

            if match:
                log.debug('found episode number with regexp %s (%s)' % (ep_re, match.groups()))
                matches = match.groups()
                if len(matches) == 2:
                    season = matches[0]
                    episode = matches[1]
                else:
                    # assume season 1 if the season was not specified
                    season = 1
                    episode = matches[0]
                    if not episode.isdigit():
                        episode = self.roman_to_int(episode)
                        # If we can't parse the roman numeral, continue the search
                        if not episode:
                            continue
                break
        else:
            return False
        return int(season), int(episode), match

    def roman_to_int(self, roman):
        """Converts roman numerals up to 39 to integers"""
        roman_map = [('X', 10), ('IX', 9), ('V', 5), ('IV', 4), ('I', 1)]
        roman = roman.upper()

        # Return False if this is not a roman numeral we can translate
        for char in roman:
            if char not in 'XVI':
                return False

        # Add up the parts of the numeral
        i = result = 0
        for numeral, integer in roman_map:
            while roman[i:i + len(numeral)] == numeral:
                result += integer
                i += len(numeral)
        return result

    @property
    def identifier(self):
        """Return String identifier for parsed episode, eg. S01E02"""
        if not self.valid:
            raise Exception('Series flagged invalid')
        if isinstance(self.season, int) and isinstance(self.episode, int):
            return 'S%sE%s' % (str(self.season).zfill(2), str(self.episode).zfill(2))
        elif self.id is None:
            raise Exception('Series is missing identifier')
        else:
            return self.id

    @property
    def proper(self):
        return self.proper_or_repack

    def __str__(self):
        # for some fucking reason it's impossible to print self.field here, if someone figures out why please
        # tell me!
        valid = 'INVALID'
        if self.valid:
            valid = 'OK'
        return '<SeriesParser(data=%s,name=%s,id=%s,season=%s,episode=%s,quality=%s,proper=%s,status=%s)>' % \
            (self.data, self.name, str(self.id), self.season, self.episode, \
             self.quality, self.proper_or_repack, valid)

    def __cmp__(self, other):
        """
        me = (self.qualities.index(self.quality), self.name)
        other = (self.qualities.index(other.quality), other.name)
        return cmp(me, other)
        """
        return cmp(qualities.get(self.quality).value, qualities.get(other.quality).value)

    def __eq__(self, other):
        return self is other
