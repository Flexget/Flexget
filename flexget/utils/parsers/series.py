import re
from datetime import datetime, timedelta
from string import capwords

from dateutil.parser import parse as parsedate
from loguru import logger

from flexget.utils import qualities
from flexget.utils.parsers.generic import ParseWarning, default_ignore_prefixes, name_to_re
from flexget.utils.parsers.parser import TitleParser
from flexget.utils.tools import ReList

logger = logger.bind(name='seriesparser')

ID_TYPES = ['ep', 'date', 'sequence', 'id']  # may also be 'special'


class SeriesParser(TitleParser):
    """
    Parse series.

    :name: series name
    :data: data to parse
    :expect_ep: expect series to be in season, ep format (ep_regexps)
    :expect_id: expect series to be in id format (id_regexps)
    """

    separators = '[/ -]'
    roman_numeral_re = 'X{0,3}(?:IX|XI{0,4}|VI{0,4}|IV|V|I{1,4})'
    english_numbers = [
        'one',
        'two',
        'three',
        'four',
        'five',
        'six',
        'seven',
        'eight',
        'nine',
        'ten',
    ]

    # Make sure none of these are found embedded within a word or other numbers
    ep_regexps = ReList(
        [
            TitleParser.re_not_in_word(regexp)
            for regexp in [
                r'(?:series|season|s)\s?(\d{1,4})(?:\s(?:.*\s)?)?(?:episode|ep|e|part|pt)\s?(\d{1,3}|%s)(?:\s?e?(\d{1,2}))?'
                % roman_numeral_re,
                r'(?:series|season)\s?(\d{1,4})\s(\d{1,3})\s?of\s?(?:\d{1,3})',
                r'(\d{1,2})\s?x\s?(\d+)(?:\s(\d{1,2}))?',
                r'(\d{1,3})\s?of\s?(?:\d{1,3})',
                r'(?:episode|e|ep|part|pt)\s?(\d{1,3}|%s)' % roman_numeral_re,
                r'part\s(%s)' % '|'.join(map(str, english_numbers)),
            ]
        ]
    )
    season_pack_regexps = ReList(
        [
            # S01 or Season 1 but not Season 1 Episode|Part 2
            r'(?:season\s?|s)(\d{1,})(?:\s|$)(?!(?:(?:.*?\s)?(?:episode|e|ep|part|pt)\s?(?:\d{1,3}|%s)|(?:\d{1,3})\s?of\s?(?:\d{1,3})))'
            % roman_numeral_re,
            r'(\d{1,3})\s?x\s?all',  # 1xAll
        ]
    )
    unwanted_regexps = ReList(
        [
            r'(\d{1,3})\s?x\s?(0+)[^1-9]',  # 5x0
            r'S(\d{1,3})D(\d{1,3})',  # S3D1
            r'(?:s|series|\b)\s?\d\s?(?:&\s?\d)?[\s-]*(?:complete|full)',
            r'disc\s\d',
        ]
    )
    # Make sure none of these are found embedded within a word or other numbers
    date_regexps = ReList(
        [
            TitleParser.re_not_in_word(regexp)
            for regexp in [
                fr'(\d{{2,4}}){separators}(\d{{1,2}}){separators}(\d{{1,2}})',
                fr'(\d{{1,2}}){separators}(\d{{1,2}}){separators}(\d{{2,4}})',
                r'(\d{4})x(\d{1,2})%s(\d{1,2})' % separators,
                fr'(\d{{1,2}})(?:st|nd|rd|th)?{separators}([a-z]{{3,10}}){separators}(\d{{4}})',
            ]
        ]
    )
    sequence_regexps = ReList(
        [
            TitleParser.re_not_in_word(regexp)
            for regexp in [
                r'(\d{1,3})(?:v(?P<version>\d))?',
                r'(?:pt|part)\s?(\d+|%s)' % roman_numeral_re,
            ]
        ]
    )
    unwanted_sequence_regexps = ReList([r'seasons?\s?\d{1,2}'])
    id_regexps = ReList([])
    clean_regexps = ReList([r'\[.*?\]', r'\(.*?\)'])
    # ignore prefix regexps must be passive groups with 0 or 1 occurrences  eg. (?:prefix)?
    ignore_prefixes = default_ignore_prefixes

    def __init__(
        self,
        name=None,
        alternate_names=None,
        identified_by='auto',
        name_regexps=None,
        ep_regexps=None,
        date_regexps=None,
        sequence_regexps=None,
        id_regexps=None,
        strict_name=False,
        allow_groups=None,
        allow_seasonless=True,
        date_dayfirst=None,
        date_yearfirst=None,
        special_ids=None,
        prefer_specials=False,
        assume_special=False,
    ):
        """
        Init SeriesParser.

        :param string name: Name of the series parser is going to try to parse. If not supplied series name will be
            guessed from data.
        :param list alternate_names: Other names for this series that should be allowed.
        :param string identified_by: What kind of episode numbering scheme is expected,
            valid values are ep, date, sequence, id and auto (default).
        :param list name_regexps: Regexps for name matching or None (default),
            by default regexp is generated from name.
        :param list ep_regexps: Regexps detecting episode,season format.
            Given list is prioritized over built-in regexps.
        :param list date_regexps: Regexps detecting date format.
            Given list is prioritized over built-in regexps.
        :param list sequence_regexps: Regexps detecting sequence format.
            Given list is prioritized over built-in regexps.
        :param list id_regexps: Custom regexps detecting id format.
            Given list is prioritized over built in regexps.
        :param boolean strict_name: If True name must be immediately be followed by episode identifier.
        :param list allow_groups: Optionally specify list of release group names that are allowed.
        :param date_dayfirst: Prefer day first notation of dates when there are multiple possible interpretations.
        :param date_yearfirst: Prefer year first notation of dates when there are multiple possible interpretations.
            This will also populate attribute `group`.
        :param special_ids: Identifiers which will cause entry to be flagged as a special.
        :param boolean prefer_specials: If True, label entry which matches both a series identifier and a special
            identifier as a special.
        """

        self.episodes = 1
        self.name = name
        self.alternate_names = alternate_names or []
        self.data = ''
        self.identified_by = identified_by
        # Stores the type of identifier found, 'ep', 'date', 'sequence' or 'special'
        self.id_type = None
        self.name_regexps = ReList(name_regexps or [])
        self.re_from_name = False
        # If custom identifier regexps were provided, prepend them to the appropriate type of built in regexps
        for mode in ID_TYPES:
            listname = mode + '_regexps'
            if locals()[listname]:
                setattr(
                    self, listname, ReList(locals()[listname] + getattr(SeriesParser, listname))
                )
        self.specials = self.specials + [i.lower() for i in (special_ids or [])]
        self.prefer_specials = prefer_specials
        self.assume_special = assume_special
        self.strict_name = strict_name
        self.allow_groups = allow_groups or []
        self.allow_seasonless = allow_seasonless
        self.date_dayfirst = date_dayfirst
        self.date_yearfirst = date_yearfirst

        self.field = None
        self._reset()

    def _reset(self):
        # parse produces these
        self.season = None
        self.episode = None
        self.episodes = 1
        self.id = None
        self.id_type = None
        self.id_groups = None
        self.quality = None
        self.proper_count = 0
        self.special = False
        # TODO: group is only produced with allow_groups
        self.group = None
        self.season_pack = None

        # false if item does not match series
        self.valid = False

    def remove_dirt(self, data):
        """Replaces some characters with spaces"""
        return re.sub(r'[_.,\[\]\(\): ]+', ' ', data).strip().lower()

    def guess_name(self):
        """This will attempt to guess a series name based on the provided data."""
        # We need to replace certain characters with spaces to make sure episode parsing works right
        # We don't remove anything, as the match positions should line up with the original title
        clean_title = re.sub(r'[_.,\[\]\(\):]', ' ', self.data)
        if self.parse_unwanted(clean_title):
            return
        match = self.parse_date(clean_title)
        if match:
            self.identified_by = 'date'
        else:
            match = self.parse_season_packs(clean_title)
            if not match:
                match = self.parse_episode(clean_title)
            self.identified_by = 'ep'
        if not match:
            return
        if match['match'].start() > 1:
            # We start using the original title here, so we can properly ignore unwanted prefixes.
            # Look for unwanted prefixes to find out where the series title starts
            start = 0
            prefix = re.match('|'.join(self.ignore_prefixes), self.data)
            if prefix:
                start = prefix.end()
            # If an episode id is found, assume everything before it is series name
            name = self.data[start : match['match'].start()]
            # Remove possible episode title from series name (anything after a ' - ')
            name = name.split(' - ')[0]
            # Replace some special characters with spaces
            name = re.sub(r'[\._\(\) ]+', ' ', name).strip(' -')
            # Normalize capitalization to title case
            name = capwords(name)
            self.name = name
            return name

    def parse(self, data=None, field=None, quality=None):
        # Clear the output variables before parsing
        self._reset()
        self.field = field
        if quality:
            self.quality = quality
        if data:
            self.data = data
        if not self.data:
            raise ParseWarning(self, 'No data supplied to parse.')
        if not self.name:
            logger.trace('No name for series `{}` supplied, guessing name.', self.data)
            if not self.guess_name():
                logger.trace('Could not determine a series name')
                return
            logger.trace('Series name for {} guessed to be {}', self.data, self.name)

        # check if data appears to be unwanted (abort)
        if self.parse_unwanted(self.remove_dirt(self.data)):
            raise ParseWarning(self, f'`{self.data}` appears to be an episode pack')

        name = self.remove_dirt(self.name)

        logger.trace('name: {} data: {}', name, self.data)

        # name end position
        name_start = 0
        name_end = 0

        # regexp name matching
        if not self.name_regexps:
            # if we don't have name_regexps, generate one from the name
            self.name_regexps = ReList(
                name_to_re(name, self.ignore_prefixes, self)
                for name in [self.name, *self.alternate_names]
            )
            # With auto regex generation, the first regex group captures the name
            self.re_from_name = True
        # try all specified regexps on this data
        for name_re in self.name_regexps:
            match = re.search(name_re, self.data)
            if match:
                match_start, match_end = match.span(1 if self.re_from_name else 0)
                # Always pick the longest matching regex
                if match_end > name_end:
                    name_start, name_end = match_start, match_end
                logger.trace('NAME SUCCESS: {} matched to {}', name_re.pattern, self.data)
        if not name_end:
            # leave this invalid
            logger.trace(
                'FAIL: name regexps {} do not match {}',
                [regexp.pattern for regexp in self.name_regexps],
                self.data,
            )
            return

        # remove series name from raw data, move any prefix to end of string
        data_stripped = self.data[name_end:] + ' ' + self.data[:name_start]
        data_stripped = data_stripped.lower()
        logger.trace('data stripped: {}', data_stripped)

        # allow group(s)
        if self.allow_groups:
            for group in self.allow_groups:
                group = group.lower()
                for fmt in ['[%s]', '-%s', '(%s)']:
                    if fmt % group in data_stripped:
                        logger.trace('{} is from group {}', self.data, group)
                        self.group = group
                        data_stripped = data_stripped.replace(fmt % group, '')
                        break
                if self.group:
                    break
            else:
                logger.trace('{} is not from groups {}', self.data, self.allow_groups)
                return  # leave invalid

        # Find quality and clean from data
        logger.trace('parsing quality ->')
        quality = qualities.Quality(data_stripped)
        if quality:
            # Remove quality string from data
            logger.trace('quality detected, using remaining data `{}`', quality.clean_text)
            data_stripped = quality.clean_text
        # Don't override passed in quality
        if not self.quality:
            self.quality = quality

        # Remove unwanted words from data for ep / id parsing
        data_stripped = self.remove_words(data_stripped, self.remove, not_in_word=True)

        data_parts = re.split(r'[\W_]+', data_stripped)

        for part in data_parts[:]:
            if part in self.propers:
                self.proper_count += 1
                data_parts.remove(part)
            elif part == 'fastsub':
                # Subtract 5 to leave room for fastsub propers before the normal release
                self.proper_count -= 5
                data_parts.remove(part)
            elif part in self.specials:
                self.special = True
                data_parts.remove(part)

        data_stripped = ' '.join(data_parts).strip()

        logger.trace("data for date/ep/id parsing '{}'", data_stripped)

        # Try date mode before ep mode
        if self.identified_by in ['date', 'auto']:
            date_match = self.parse_date(data_stripped)
            if date_match:
                if self.strict_name:
                    if date_match['match'].start() > 1:
                        return
                self.id = date_match['date']
                self.id_groups = date_match['match'].groups()
                self.id_type = 'date'
                self.valid = True
                if not (self.special and self.prefer_specials):
                    return
            else:
                logger.trace('-> no luck with date_regexps')

        if self.identified_by in ['ep', 'auto'] and not self.valid:
            ep_match = self.parse_episode(data_stripped)
            if ep_match:
                # strict_name
                if self.strict_name:
                    if ep_match['match'].start() > 1:
                        return

                if ep_match['end_episode'] and ep_match['end_episode'] > ep_match['episode'] + 2:
                    # This is a pack of too many episodes, ignore it.
                    logger.trace(
                        'Series pack contains too many episodes ({}). Rejecting',
                        ep_match['end_episode'] - ep_match['episode'],
                    )
                    return

                self.season = ep_match['season']
                self.episode = ep_match['episode']
                if ep_match['end_episode']:
                    self.episodes = (ep_match['end_episode'] - ep_match['episode']) + 1

                self.id = (self.season, self.episode)
                self.id_type = 'ep'
                self.valid = True
                if not (self.special and self.prefer_specials):
                    return
            else:
                season_pack_match = self.parse_season_packs(data_stripped)
                # If a title looks like a special, give it precedence over season pack
                if season_pack_match and not self.special:
                    if self.strict_name and season_pack_match['match'].start() > 1:
                        return
                    self.season = season_pack_match['season']
                    self.season_pack = True
                    self.id = (season_pack_match['season'], 0)
                    self.id_type = 'ep'
                    self.valid = True
                else:
                    logger.trace('-> no luck with ep_regexps')

            if self.identified_by == 'ep' and not self.season_pack:
                # we should be getting season, ep !
                # try to look up idiotic numbering scheme 101,102,103,201,202
                # ressu: Added matching for 0101, 0102... It will fail on
                #        season 11 though
                logger.trace('ep identifier expected. Attempting SEE format parsing.')
                # remove obvious date format from this desperate try
                desperate = re.sub(r'\d{4}\s\d{1,2}\s\d{1,2}', '', data_stripped)
                match = re.search(
                    self.re_not_in_word(r'(\d?\d)(\d\d)'),
                    desperate,
                    re.IGNORECASE | re.UNICODE,
                )
                if match:
                    logger.trace('-> had luck with SEE')
                    # strict_name
                    if self.strict_name:
                        if match.start() > 1:
                            return

                    self.season = int(match.group(1))
                    self.episode = int(match.group(2))
                    self.id = (self.season, self.episode)
                    logger.trace(self)
                    self.id_type = 'ep'
                    self.valid = True
                    return
                else:
                    logger.trace('-> no luck with SEE')

        # Check id regexps
        if self.identified_by in ['id', 'auto'] and not self.valid:
            for id_re in self.id_regexps:
                match = re.search(id_re, data_stripped)
                if match:
                    # strict_name
                    if self.strict_name:
                        if match.start() > 1:
                            return
                    found_id = '-'.join(g for g in match.groups() if g)
                    if not found_id:
                        # If match groups were all blank, don't accept this match
                        continue
                    self.id = found_id
                    self.id_type = 'id'
                    self.valid = True
                    logger.trace("found id '{}' with regexp '{}'", self.id, id_re.pattern)
                    if not (self.special and self.prefer_specials):
                        return
                    else:
                        break
            else:
                logger.trace('-> no luck with id_regexps')

        # Other modes are done, check for unwanted sequence ids
        if self.parse_unwanted_sequence(data_stripped):
            return

        # Check sequences last as they contain the broadest matches
        if self.identified_by in ['sequence', 'auto'] and not self.valid:
            for sequence_re in self.sequence_regexps:
                match = re.search(sequence_re, data_stripped)
                if match:
                    # strict_name
                    if self.strict_name:
                        if match.start() > 1:
                            return
                    # First matching group is the sequence number
                    try:
                        self.id = int(match.group(1))
                    except ValueError:
                        self.id = self.roman_to_int(match.group(1))
                    self.season = 0
                    self.episode = self.id
                    # If anime style version was found, overwrite the proper count with it
                    if 'version' in match.groupdict():
                        if match.group('version'):
                            self.proper_count = int(match.group('version')) - 1
                    self.id_type = 'sequence'
                    self.valid = True
                    logger.trace("found id '{}' with regexp '{}'", self.id, sequence_re.pattern)
                    if not (self.special and self.prefer_specials):
                        return
                    else:
                        break
            else:
                logger.trace('-> no luck with sequence_regexps')

        # No id found, check if this is a special
        if self.special or self.assume_special:
            # Attempt to set id as the title of the special
            self.id = data_stripped or 'special'
            self.id_type = 'special'
            self.valid = True
            logger.trace("found special, setting id to '{}'", self.id)
            return
        if self.valid:
            return

        msg = f'Title `{self.data}` looks like series `{self.name}` but cannot find '
        if self.identified_by == 'auto':
            msg += 'any series numbering.'
        else:
            msg += 'a(n) `%s` style identifier.' % self.identified_by
        raise ParseWarning(self, msg)

    def parse_unwanted(self, data):
        """Parses data for an unwanted hits. Return True if the data contains unwanted hits."""
        for unwanted_re in self.unwanted_regexps:
            match = re.search(unwanted_re, data)
            if match:
                logger.trace('unwanted regexp {} matched {}', unwanted_re.pattern, match.groups())
                return True

    def parse_unwanted_sequence(self, data):
        """Parses data for an unwanted id hits. Return True if the data contains unwanted hits."""
        for seq_unwanted_re in self.unwanted_sequence_regexps:
            match = re.search(seq_unwanted_re, data)
            if match:
                logger.trace('unwanted id regexp {} matched {}', seq_unwanted_re, match.groups())
                return True

    def parse_date(self, data):
        """
        Parses :data: for a date identifier.
        If found, returns the date and regexp match object
        If no date is found returns False
        """
        for date_re in self.date_regexps:
            match = re.search(date_re, data)
            if match:
                # Check if this is a valid date
                possdates = []

                try:
                    # By default dayfirst and yearfirst will be tried as both True and False
                    # if either have been defined manually, restrict that option
                    dayfirst_opts = [True, False]
                    if self.date_dayfirst is not None:
                        dayfirst_opts = [self.date_dayfirst]
                    yearfirst_opts = [True, False]
                    if self.date_yearfirst is not None:
                        yearfirst_opts = [self.date_yearfirst]
                    kwargs_list = (
                        {'dayfirst': d, 'yearfirst': y}
                        for d in dayfirst_opts
                        for y in yearfirst_opts
                    )
                    for kwargs in kwargs_list:
                        possdate = parsedate(' '.join(match.groups()), **kwargs)
                        # Don't accept dates farther than a day in the future
                        if possdate > datetime.now() + timedelta(days=1):
                            continue
                        # Don't accept dates that are too old
                        if possdate < datetime(1970, 1, 1):
                            continue
                        if possdate not in possdates:
                            possdates.append(possdate)
                except ValueError:
                    logger.trace('{} is not a valid date, skipping', match.group(0))
                    continue
                if not possdates:
                    logger.trace('All possible dates for {} were in the future', match.group(0))
                    continue
                possdates.sort()
                # Pick the most recent date if there are ambiguities
                bestdate = possdates[-1]
                return {'date': bestdate, 'match': match}

        return False

    def parse_episode(self, data):
        """
        Parses :data: for an episode identifier.
        If found, returns a dict with keys for season, episode, end_episode and the regexp match object
        If no episode id is found returns False
        """

        # search for season and episode number
        for ep_re in self.ep_regexps:
            match = re.search(ep_re, data)

            if match:
                logger.trace(
                    'found episode number with regexp {} ({})', ep_re.pattern, match.groups()
                )
                matches = match.groups()
                if len(matches) >= 2:
                    season = matches[0]
                    episode = matches[1]
                elif self.allow_seasonless:
                    # assume season 1 if the season was not specified
                    season = 1
                    episode = matches[0]
                else:
                    # Return False if we are not allowing seasonless matches and one is found
                    return False
                # Convert season and episode to integers
                try:
                    season = int(season)
                    if not episode.isdigit():
                        try:
                            idx = self.english_numbers.index(str(episode).lower())
                            episode = 1 + idx
                        except ValueError:
                            episode = self.roman_to_int(episode)
                    else:
                        episode = int(episode)
                except ValueError:
                    logger.critical(
                        'Invalid episode number match {} returned with regexp `{}` for {}',
                        match.groups(),
                        ep_re.pattern,
                        self.data,
                    )
                    raise
                end_episode = None
                if len(matches) == 3 and matches[2]:
                    end_episode = int(matches[2])
                    if end_episode <= episode or end_episode > episode + 12:
                        # end episode cannot be before start episode
                        # Assume large ranges are not episode packs, ticket #1271 TODO: is this the best way?
                        end_episode = None
                # Successfully found an identifier, return the results
                return {
                    'season': season,
                    'episode': episode,
                    'end_episode': end_episode,
                    'match': match,
                }
        return False

    def parse_season_packs(self, data):
        """Parses data for season packs. Return True if the data contains a hit"""
        for season_pack_re in self.season_pack_regexps:
            match = re.search(season_pack_re, data)
            if match:
                logger.trace(
                    'season pack regexp {} match {}', season_pack_re.pattern, match.groups()
                )
                matches = match.groups()
                if len(matches) == 1:
                    # Single season full pack, no parts etc
                    season = int(matches[0])
                    return {'season': season, 'match': match}
                elif len(matches) == 2:
                    # TODO support other formats of season packs: 1xall, s01-PART1, etc.
                    pass

    def roman_to_int(self, roman):
        """Converts roman numerals up to 39 to integers"""

        roman_map = [('X', 10), ('IX', 9), ('V', 5), ('IV', 4), ('I', 1)]
        roman = roman.upper()

        # Return False if this is not a roman numeral we can translate
        for char in roman:
            if char not in 'XVI':
                raise ValueError('`%s` is not a valid roman numeral' % roman)

        # Add up the parts of the numeral
        i = result = 0
        for numeral, integer in roman_map:
            while roman[i : i + len(numeral)] == numeral:
                result += integer
                i += len(numeral)
        return result

    def __str__(self):
        # for some fucking reason it's impossible to print self.field here, if someone figures out why please
        # tell me!
        valid = 'INVALID'
        if self.valid:
            valid = 'OK'
        return (
            '<SeriesParser(data={},name={},id={},id_type={},identified_by={},season={},season_pack={},episode={},quality={},proper={},'
            'status={})>'.format(
                self.data,
                self.name,
                str(self.id),
                self.id_type,
                self.identified_by,
                self.season,
                self.season_pack,
                self.episode,
                self.quality,
                self.proper_count,
                valid,
            )
        )
