from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.utils import native

import logging
import re
import sys
import time

from guessit.rules import rebulk_builder
from guessit.api import GuessItApi, GuessitException
from rebulk import Rebulk
from rebulk.pattern import RePattern

from flexget import plugin
from flexget.event import event
from flexget.utils import qualities
from flexget.utils.tools import ReList
from .parser_common import MovieParseResult, SeriesParseResult

log = logging.getLogger('parser_guessit')

logging.getLogger('rebulk').setLevel(logging.WARNING)
logging.getLogger('guessit').setLevel(logging.WARNING)


def _id_regexps_function(input_string, context):
    ret = []
    for regexp in context.get('id_regexps'):
        for match in RePattern(regexp, children=True).matches(input_string, context):
            ret.append(match.span)
    return ret


default_ignore_prefixes = [
    '(?:\[[^\[\]]*\])',  # ignores group names before the name, eg [foobar] name
    '(?:HD.720p?:)',
    '(?:HD.1080p?:)',
    '(?:HD.2160p?:)'
]


def name_to_re(name, ignore_prefixes=None, parser=None):
    """Convert 'foo bar' to '^[^...]*foo[^...]*bar[^...]+"""
    if not ignore_prefixes:
        ignore_prefixes = default_ignore_prefixes
    parenthetical = None
    if name.endswith(')'):
        p_start = name.rfind('(')
        if p_start != -1:
            parenthetical = re.escape(name[p_start + 1:-1])
            name = name[:p_start - 1]
    # Blanks are any non word characters except & and _
    blank = r'(?:[^\w&]|_)'
    ignore = '(?:' + '|'.join(ignore_prefixes) + ')?'
    res = re.sub(re.compile(blank + '+', re.UNICODE), ' ', name)
    res = res.strip()
    # accept either '&' or 'and'
    res = re.sub(' (&|and) ', ' (?:and|&) ', res, re.UNICODE)
    res = re.sub(' +', blank + '*', res, re.UNICODE)
    if parenthetical:
        res += '(?:' + blank + '+' + parenthetical + ')?'
        # Turn on exact mode for series ending with a parenthetical,
        # so that 'Show (US)' is not accepted as 'Show (UK)'
        if parser:
            parser.strict_name = True
    res = '^' + ignore + blank + '*' + '(' + res + ')(?:\\b|_)' + blank + '*'
    return res


_id_regexps = Rebulk().functional(_id_regexps_function, name='regexpId',
                                  disabled=lambda context: not context.get('id_regexps'))

guessit_api = GuessItApi(rebulk_builder().rebulk(_id_regexps))


class ParserGuessit(object):
    @staticmethod
    def _guessit_options(options):
        settings = {'name_only': True, 'allowed_languages': ['en', 'fr'], 'allowed_countries': ['us', 'uk', 'gb']}
        # 'clean_function': clean_value
        options['episode_prefer_number'] = not options.get('identified_by') == 'ep'
        if options.get('allow_groups'):
            options['expected_group'] = options['allow_groups']
        if 'date_yearfirst' in options:
            options['date_year_first'] = options['date_yearfirst']
        if 'date_dayfirst' in options:
            options['date_day_first'] = options['date_dayfirst']
        settings.update(options)
        return settings

    @staticmethod
    def _proper_count(guessit_result):
        """Calculate a FlexGet style proper_count from a guessit result."""
        version = guessit_result.get('version')
        if version is None:
            version = 0
        elif version <= 0:
            version = -1
        else:
            version -= 1
        proper_count = guessit_result.get('proper_count', 0)
        fastsub = 'Fastsub' in guessit_result.get('other', [])
        return version + proper_count - (5 if fastsub else 0)

    @staticmethod
    def _quality(guessit_result):
        """Generate a FlexGet Quality from a guessit result."""
        resolution = guessit_result.get('screen_size', '')
        if not resolution and 'HR' in guessit_result.get('other', []):
            resolution = 'hr'

        source = guessit_result.get('format', '').replace('-', '')
        if 'Preair' in guessit_result.get('other', {}):
            source = 'preair'
        if 'Screener' in guessit_result.get('other', {}):
            if source == 'BluRay':
                source = 'bdscr'
            else:
                source = 'dvdscr'
        if 'R5' in guessit_result.get('other', {}):
            source = 'r5'

        codec = guessit_result.get('video_codec', '')
        if guessit_result.get('video_profile') == '10bit':
            codec = '10bit'

        audio = guessit_result.get('audio_codec', '')
        if audio == 'DTS' and guessit_result.get('audio_profile') in ['HD', 'HDMA']:
            audio = 'dtshd'
        elif guessit_result.get('audio_channels') == '5.1' and not audio or audio == 'DolbyDigital':
            audio = 'dd5.1'

        return qualities.Quality(' '.join([resolution, source, codec, audio]))

    # movie_parser API
    def parse_movie(self, data, **kwargs):
        log.debug('Parsing movie: `%s` [options: %s]', data, kwargs)
        start = time.clock()
        guessit_options = self._guessit_options(kwargs)
        guessit_options['type'] = 'movie'
        guess_result = guessit_api.guessit(data, options=guessit_options)
        # NOTE: Guessit expects str on PY3 and unicode on PY2 hence the use of future.utils.native
        parsed = MovieParseResult(
            data=data,
            name=guess_result.get('title'),
            year=guess_result.get('year'),
            proper_count=self._proper_count(guess_result),
            quality=self._quality(guess_result)
        )
        end = time.clock()
        log.debug('Parsing result: %s (in %s ms)', parsed, (end - start) * 1000)
        return parsed

    # series_parser API
    def parse_series(self, data, **kwargs):
        log.debug('Parsing series: `%s` [options: %s]', data, kwargs)
        guessit_options = self._guessit_options(kwargs)
        if kwargs.get('name'):
            expected_titles = [kwargs['name']]
            if kwargs.get('alternate_names'):
                expected_titles.extend(kwargs['alternate_names'])
            # apostrophe support
            expected_titles = [title.replace('\'', '(?:\'|\\\'|\\\\\'|-|)?') for title in expected_titles]
            guessit_options['expected_title'] = ['re:' + title for title in expected_titles]
        if kwargs.get('id_regexps'):
            guessit_options['id_regexps'] = kwargs.get('id_regexps')
        start = time.clock()
        # If no series name is provided, we don't tell guessit what kind of match we are looking for
        # This prevents guessit from determining that too general of matches are series
        parse_type = 'episode' if kwargs.get('name') else None
        if parse_type:
            guessit_options['type'] = parse_type

        # NOTE: Guessit expects str on PY3 and unicode on PY2 hence the use of future.utils.native
        try:
            guess_result = guessit_api.guessit(native(data), options=guessit_options)
        except GuessitException:
            log.warning('Parsing %s with guessit failed. Most likely a unicode error.', data)
            guess_result = {}

        if guess_result.get('type') != 'episode':
            return SeriesParseResult(data=data, valid=False)

        name = kwargs.get('name')
        country = guess_result.get('country')
        if not name:
            name = guess_result.get('title')
            if country and hasattr(country, 'alpha2'):
                name += ' (%s)' % country.alpha2
        else:
            # Make sure the name match is up to FlexGet standards
            # Check there is no unmatched cruft before the matched name
            title_start = guess_result.matches['title'][0].start
            title_end = guess_result.matches['title'][0].end
            if title_start != 0:
                pre_title = max((match[0].end for match in guess_result.matches.values() if match[0].end <= title_start), default=0)
                for char in reversed(data[pre_title:title_start]):
                    if char.isalnum() or char.isdigit():
                        return SeriesParseResult(data=data, valid=False)
                    if char.isspace() or char in '._':
                        continue
                    else:
                        break
            # Check the name doesn't end mid-word (guessit might put the border before or after the space after title)
            if data[title_end - 1].isalnum() and len(data) <= title_end or \
                    not self._is_valid_name(data, guessit_options=guessit_options):
                return SeriesParseResult(data=data, valid=False)
            # If we are in exact mode, make sure there is nothing after the title
            if kwargs.get('strict_name'):
                post_title = sys.maxsize
                for match_type, matches in guess_result.matches.items():
                    if match_type in ['season', 'episode', 'date', 'regexpId']:
                        if matches[0].start < title_end:
                            continue
                        post_title = min(post_title, matches[0].start)
                        if matches[0].parent:
                            post_title = min(post_title, matches[0].parent.start)
                for char in data[title_end:post_title]:
                    if char.isalnum() or char.isdigit():
                        return SeriesParseResult(data=data, valid=False)
        season = guess_result.get('season')
        episode = guess_result.get('episode')
        if episode is None and 'part' in guess_result:
            episode = guess_result['part']
        date = guess_result.get('date')
        quality = self._quality(guess_result)
        proper_count = self._proper_count(guess_result)
        group = guess_result.get('release_group')
        # Validate group with from_group
        if not self._is_valid_groups(group, guessit_options.get('allow_groups', [])):
            return SeriesParseResult(data=data, valid=False)
        # Validate country, TODO: LEGACY
        if country and name.endswith(')'):
            p_start = name.rfind('(')
            if p_start != -1:
                parenthetical = re.escape(name[p_start + 1:-1])
                if parenthetical and parenthetical.lower() != str(country).lower():
                    return SeriesParseResult(data=data, valid=False)
        special = guess_result.get('episode_details', '').lower() == 'special'
        if 'episode' not in guess_result.values_list:
            episodes = len(guess_result.values_list.get('part', []))
        else:
            episodes = len(guess_result.values_list['episode'])
        if episodes > 3:
            return SeriesParseResult(data=data, valid=False)
        identified_by = kwargs.get('identified_by', 'auto')
        id_type, id = None, None
        if identified_by in ['date', 'auto']:
            if date:
                id_type = 'date'
                id = date
        if not id_type and identified_by in ['ep', 'auto']:
            if episode is not None:
                if season is None and kwargs.get('allow_seasonless', True):
                    if 'part' in guess_result:
                        season = 1
                    else:
                        episode_raw = guess_result.matches['episode'][0].initiator.raw
                        if episode_raw and any(c.isalpha() and c.lower() != 'v' for c in episode_raw):
                            season = 1
                if season is not None:
                    id_type = 'ep'
                    id = (season, episode)

        if not id_type and identified_by in ['id', 'auto']:
            if guess_result.matches['regexpId']:
                id_type = 'id'
                id = '-'.join(match.value for match in guess_result.matches['regexpId'])
        if not id_type and identified_by in ['sequence', 'auto']:
            if episode is not None:
                id_type = 'sequence'
                id = episode
        if (not id_type or guessit_options.get('prefer_specials')) and (special or
                                                                        guessit_options.get('assume_special')):
            id_type = 'special'
            id = guess_result.get('episode_title', 'special')
        if not id_type:
            return SeriesParseResult(data=data, valid=False)

        parsed = SeriesParseResult(
            data=data,
            name=name,
            episodes=episodes,
            identified_by=identified_by,
            id=id,
            id_type=id_type,
            quality=quality,
            proper_count=proper_count,
            special=special,
            group=group
        )

        end = time.clock()
        log.debug('Parsing result: %s (in %s ms)', parsed, (end - start) * 1000)
        return parsed

    # TODO: The following functions are sort of legacy. No idea if they should be changed.
    def _is_valid_name(self, data, guessit_options):
        # name end position
        name_start = 0
        name_end = 0

        # regexp name matching
        re_from_name = False
        name_regexps = ReList(guessit_options.get('name_regexps', []))
        if not name_regexps:
            # if we don't have name_regexps, generate one from the name
            name_regexps = ReList(name_to_re(name, default_ignore_prefixes, None)
                                  for name in [guessit_options['name']] + guessit_options.get('alternate_names', []))
            # With auto regex generation, the first regex group captures the name
            re_from_name = True
        # try all specified regexps on this data
        for name_re in name_regexps:
            match = re.search(name_re, data)
            if match:
                match_start, match_end = match.span(1 if re_from_name else 0)
                # Always pick the longest matching regex
                if match_end > name_end:
                    name_start, name_end = match_start, match_end
                log.debug('NAME SUCCESS: %s matched to %s', name_re.pattern, data)
        if not name_end:
            # leave this invalid
            log.debug('FAIL: name regexps %s do not match %s',
                      [regexp.pattern for regexp in name_regexps], data)
            return
        return True

    def _is_valid_groups(self, group, allow_groups):
        if not allow_groups:
            return True
        if not group:
            return False
        return group.lower() in [x.lower() for x in allow_groups]


@event('plugin.register')
def register_plugin():
    plugin.register(ParserGuessit, 'parser_guessit', interfaces=['movie_parser', 'series_parser'], api_ver=2)
