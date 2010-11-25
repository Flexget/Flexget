import logging
import re
from flexget.utils.titles.parser import TitleParser, ParseWarning
from flexget.utils import qualities

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

    def __init__(self):
        # parser settings
        self.name = ''
        self.data = ''
        self.expect_ep = False
        self.expect_id = False
        self.allow_groups = []

        # if set to true, episode or id must follow immediately after name
        self.strict_name = False

        separators = '[!/+,:;|~ x-]'
        roman_numeral_re = 'X{0,3}(?:IX|XI{0,4}|VI{0,4}|IV|V|I{1,4})'
        self.ep_regexps = [
                '(?:series|season|s)\s?(\d{1,3})(?:\s(?:.*?\s)?)?(?:episode|ep|e|part|pt)\s?(\d{1,3}|%s)' % roman_numeral_re,
                '(?:series|season)\s?(\d{1,3})\s(\d{1,3})\s?of\s?(?:\d{1,3})',
                '(\d{1,3})\s?of\s?(?:\d{1,3})',
                '(\d{1,2})\s?x\s?(\d+)',
                '(?:episode|ep|part|pt)\s?(\d{1,3}|%s)' % roman_numeral_re]
        self.unwanted_ep_regexps = [
                 '(\d{1,3})\s?x\s?(0+)[^1-9]', # 5x0
                 'S(\d{1,3})D(\d{1,3})', # S3D1
                 '(\d{1,3})\s?x\s?(all)', # 1xAll
                 'season(?:s)?\s?\d\s?(?:&\s?\d)?[\s-]*(?:complete|full)',
                 'seasons\s(\d\s){2,}',
                 'disc\s\d',
                 's\d+.?e\d+-\d+'] # S6 E1-4
        self.id_regexps = [
                '(\d{4})%s(\d+)%s(\d+)' % (separators, separators),
                '(\d+)%s(\d+)%s(\d{4})' % (separators, separators),
                '(\d{4})x(\d+)\.(\d+)', '(pt|part)\s?(\d+|%s)' % roman_numeral_re,
                '(?:^|[^s\d])(\d{1,3})(?:[^p\d]|$)']
        self.clean_regexps = ['\[.*?\]', '\(.*?\)']
        # ignore prefix regexpes must be passive groups with 0 or 1 occurrences  eg. (?:prefix)?
        self.ignore_prefix_regexps = [
                '(?:\[[^\[\]]*\])', # ignores group names before the name, eg [foobar] name
                '(?:HD.720p?:)',
                '(?:HD.1080p?:)']
        self.name_regexps = []

        self.field = None

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
        """Convert name and data to unicode transparently"""
        if name == 'name' or name == 'data':
            if isinstance(value, str):
                object.__setattr__(self, name, unicode(value))
                return
            elif not isinstance(value, unicode):
                raise Exception('%s cannot be %s' % (name, repr(value)))
        object.__setattr__(self, name, value)

    def clean(self, data):
        """Perform data cleaner regexps"""
        for clean_re in self.clean_regexps:
            matches = re.findall(clean_re, data, re.IGNORECASE | re.UNICODE)
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

    def parse(self):
        if not self.name or not self.data:
            raise Exception('SeriesParser initialization error, name: %s data: %s' % \
               (repr(self.name), repr(self.data)))

        if self.expect_ep and self.expect_id:
            raise Exception('Flags expect_ep and expect_id are mutually exclusive')

        name = self.remove_dirt(self.name)

        # check if data appears to be unwanted (abort)
        if self.parse_unwanted(self.remove_dirt(self.clean(self.data))):
            return

        def name_to_re(name):
            """Convert 'foo bar' to '^[^...]*foo[^...]*bar[^...]+"""
            # TODO: Still doesn't handle the case where the user wants
            # "Schmost" and the feed contains "Schmost at Sea".
            blank = r'[^0-9a-zA-Z]'
            ignore = '(?:' + '|'.join(self.ignore_prefix_regexps) + ')?'
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
        re_from_name = False
        if not self.name_regexps:
            # if we don't have name_regexps, generate one from the name
            self.name_regexps = [name_to_re(name)]
            re_from_name = True
            if '&' in name:
                # if & is in the name, also add a regexp that accepts 'and' instead
                self.name_regexps.append(name_to_re(name.replace('&', 'and')))
        # use all specified regexps to this data
        for name_re in self.name_regexps:
            match = re.search(name_re, self.data, re.IGNORECASE | re.UNICODE)
            if match:
                if re_from_name:
                    name_start, name_end = match.span(1)
                else:
                    name_start, name_end = match.span()
                break
        else:
            # leave this invalid
            log.debug('FAIL: name regexps do not match')
            return


        # remove series name from raw data, move any prefix to end of string
        data_noname = self.data[name_end:] + ' ' + self.data[:name_start]
        data_noname = data_noname.lower()
        log.debug('data noname: %s' % data_noname)

        # allow group(s)
        if self.allow_groups:
            for group in self.allow_groups:
                group = group.lower()
                for fmt in ['[%s]', '-%s']:
                    if fmt % group in data_noname:
                        log.debug('%s is from group %s' % (self.data, group))
                        self.group = group
                        data_noname = data_noname.replace(fmt % group, '')
                        break
                if self.group:
                    break
            else:
                log.debug('%s is not from groups %s' % (self.data, self.allow_groups))
                return # leave invalid

        # search tags and quality
        if self.quality == 'unknown':
            log.debug('parsing quality ->')
            quality, match = qualities.quality_match(data_noname)
            self.quality = quality.name
            if match:
                # Remove quality string from data
                data_noname = data_noname[:match.start()] + data_noname[match.end():]

        # Remove unwanted words (qualities and such) from data for ep / id
        data = self.remove_words(data_noname, self.remove + qualities.registry.keys() + self.codecs + self.sounds)
        data = self.clean(data)
        data = self.remove_dirt(data)

        data_parts = re.split('\W+', data)

        for part in data_parts:
            if part in self.propers:
                self.proper_or_repack = True
                data_parts.remove(part)
            if part in self.specials:
                self.special = True
                data_parts.remove(part)

        data = ' '.join(data_parts)

        log.debug("data for id/ep parsing '%s'" % data)

        ep_match = self.parse_episode(data)
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
            match = re.search('(?:^|\D)(0?\d)(\d\d)\D', data, re.IGNORECASE | re.UNICODE)
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
            for id_re in self.id_regexps:
                match = re.search(id_re, data, re.IGNORECASE | re.UNICODE)
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

        raise ParseWarning('Title \'%s\' looks like series \'%s\' but I cannot find any episode or id numbering' % (self.data, self.name))

    def parse_unwanted(self, data):
        """Parses data for an unwanted hits. Return True if the data contains unwanted hits."""
        for ep_unwanted_re in self.unwanted_ep_regexps:
            match = re.search(ep_unwanted_re, data, re.IGNORECASE | re.UNICODE)
            if match:
                log.debug('unwanted regexp %s matched %s' % (ep_unwanted_re, match.groups()))
                return True

    def parse_episode(self, data):
        """
        Parses data for an episode identifier.
        If found, returns a tuple of season#, episode# and the regexp match object
        If no episode id is found returns False
        """

        # Make sure there are non alphanumeric characters surrounding our identifier
        (lcap, rcap) = (r'(?<![a-zA-Z0-9])', r'(?![a-zA-Z0-9])')
        # search for season and episode number
        for ep_re in self.ep_regexps:
            match = re.search(lcap + ep_re + rcap, data, re.IGNORECASE | re.UNICODE)

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
        return (int(season), int(episode), match)

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
        """Return identifier for parsed episode"""
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
