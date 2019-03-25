from __future__ import absolute_import, division, unicode_literals
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from future.utils import native

import logging
import re
import sys
import time

from guessit.api import GuessItApi, GuessitException
from guessit.rules import rebulk_builder
from rebulk import Rebulk
from rebulk.match import MatchesDict
from rebulk.pattern import RePattern

from flexget import plugin
from flexget.event import event
from flexget.utils import qualities
from flexget.utils.parsers.generic import ParseWarning, default_ignore_prefixes, name_to_re
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


_id_regexps = Rebulk().functional(
    _id_regexps_function, name='regexpId', disabled=lambda context: not context.get('id_regexps')
)


def rules_builder(config):
    rebulk = rebulk_builder(config)
    rebulk.rebulk(_id_regexps)
    return rebulk


guessit_api = GuessItApi()
guessit_api.configure(options={}, rules_builder=rules_builder, force=True)


def normalize_component(data):
    if data is None:
        return []
    if isinstance(data, list):
        return [d.lower().replace('-', '') for d in data]

    return [data.lower().replace('-', '')]


try:
    preferred_clock = time.process_time
except AttributeError:
    preferred_clock = time.clock


class ParserGuessit(object):
    SOURCE_MAP = {
        'Camera': 'cam',
        'HD Camera': 'cam',
        'HD Telesync': 'telesync',
        'Pay-per-view': 'ppv',
        'Digital TV': 'dvb',
        'Video on Demand': 'vod',
        'Analog HDTV': 'ahdtv',
        'Ultra HDTV': 'uhdtv',
        'HD Telecine': 'hdtc',
        'Web': 'web-dl',
    }

    @staticmethod
    def _guessit_options(options):
        settings = {
            'name_only': True,
            'allowed_languages': ['en', 'fr'],
            'allowed_countries': ['us', 'uk', 'gb'],
            'single_value': True,
        }
        options['episode_prefer_number'] = not options.get('identified_by') == 'ep'
        if options.get('allow_groups'):
            options['expected_group'] = options['allow_groups']
        if 'date_yearfirst' in options:
            options['date_year_first'] = options['date_yearfirst']
        if 'date_dayfirst' in options:
            options['date_day_first'] = options['date_dayfirst']
        else:
            # See https://github.com/guessit-io/guessit/issues/329
            # https://github.com/guessit-io/guessit/pull/333
            # They made changes that break backward compatibility, so we have to make do this hackery
            if options.get('date_year_first'):
                options['date_day_first'] = True
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
        fastsub = 'fast subtitled' in normalize_component(guessit_result.values_list.get('other'))
        return version + proper_count - (5 if fastsub else 0)

    def _source(self, guessit_result):
        other = normalize_component(guessit_result.values_list.get('other'))
        source = self.SOURCE_MAP.get(guessit_result.get('source'), guessit_result.get('source'))
        # special case
        if source == 'web-dl' and 'rip' in other:
            source = 'webrip'

        source = normalize_component(source)

        if 'preair' in other:
            source.append('preair')
        if 'screener' in other:
            if 'bluray' in source:
                source.append('bdscr')
            else:
                source.append('dvdscr')
        if 'region 5' in other or 'region c' in other:
            source.append('r5')

        return source

    def _quality(self, guessit_result):
        """Generate a FlexGet Quality from a guessit result."""
        resolution = normalize_component(guessit_result.values_list.get('screen_size'))
        other = normalize_component(guessit_result.values_list.get('other'))
        if not resolution and 'high resolution' in other:
            resolution.append('hr')

        source = self._source(guessit_result)

        codec = normalize_component(guessit_result.values_list.get('video_codec'))
        if '10bit' in normalize_component(guessit_result.values_list.get('color_depth')):
            codec.append('10bit')

        audio = normalize_component(guessit_result.values_list.get('audio_codec'))
        audio_profile = normalize_component(guessit_result.values_list.get('audio_profile'))
        audio_channels = normalize_component(guessit_result.values_list.get('audio_channels'))
        # unlike the other components, audio can be a bit iffy with multiple codecs, so we limit it to one
        if 'dts' in audio and any(hd in audio_profile for hd in ['hd', 'master audio']):
            audio = ['dtshd']
        elif '5.1' in audio_channels and 'dolby digital plus' in audio:
            audio = ['dd+5.1']
        elif '5.1' in audio_channels and 'dolby digital' in audio:
            audio = ['dd5.1']

        # Make sure everything are strings (guessit will return lists when there are multiples)
        flattened_qualities = []
        for component in (resolution, source, codec, audio):
            if isinstance(component, list):
                flattened_qualities.append(' '.join(component))
            elif isinstance(component, str):
                flattened_qualities.append(component)
            else:
                raise ParseWarning(
                    self,
                    'Guessit quality returned type {}: {}. Expected str or list.'.format(
                        type(component), component
                    ),
                )

        return qualities.Quality(' '.join(flattened_qualities))

    # movie_parser API
    def parse_movie(self, data, **kwargs):
        log.debug('Parsing movie: `%s` [options: %s]', data, kwargs)
        start = preferred_clock()
        guessit_options = self._guessit_options(kwargs)
        guessit_options['type'] = 'movie'
        guess_result = guessit_api.guessit(data, options=guessit_options)
        # NOTE: Guessit expects str on PY3 and unicode on PY2 hence the use of future.utils.native
        parsed = MovieParseResult(
            data=data,
            name=guess_result.get('title'),
            year=guess_result.get('year'),
            proper_count=self._proper_count(guess_result),
            quality=self._quality(guess_result),
            release_group=guess_result.get('release_group'),
            valid=bool(
                guess_result.get('title')
            ),  # It's not valid if it didn't find a name, which sometimes happens
        )
        log.debug('Parsing result: %s (in %s ms)', parsed, (preferred_clock() - start) * 1000)
        return parsed

    # series_parser API
    def parse_series(self, data, **kwargs):
        log.debug('Parsing series: `%s` [options: %s]', data, kwargs)
        guessit_options = self._guessit_options(kwargs)
        valid = True
        if kwargs.get('name'):
            expected_titles = [kwargs['name']]
            if kwargs.get('alternate_names'):
                expected_titles.extend(kwargs['alternate_names'])
            # apostrophe support
            expected_titles = [
                title.replace('\'', '(?:\'|\\\'|\\\\\'|-|)?') for title in expected_titles
            ]
            guessit_options['expected_title'] = ['re:' + title for title in expected_titles]
        if kwargs.get('id_regexps'):
            guessit_options['id_regexps'] = kwargs.get('id_regexps')
        start = preferred_clock()
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
            return SeriesParseResult(data=data, valid=False)

        if guess_result.get('type') != 'episode':
            valid = False

        name = kwargs.get('name')
        country = guess_result.get('country')
        if not name:
            name = guess_result.get('title')
            if not name:
                valid = False
            elif country and hasattr(country, 'alpha2'):
                name += ' (%s)' % country.alpha2
        elif guess_result.matches['title']:
            # Make sure the name match is up to FlexGet standards
            # Check there is no unmatched cruft before the matched name
            title_start = guess_result.matches['title'][0].start
            title_end = guess_result.matches['title'][0].end
            if title_start != 0:
                try:
                    pre_title = max(
                        (
                            match[0].end
                            for match in guess_result.matches.values()
                            if match[0].end <= title_start
                        )
                    )
                except ValueError:
                    pre_title = 0
                for char in reversed(data[pre_title:title_start]):
                    if char.isalnum() or char.isdigit():
                        return SeriesParseResult(data=data, valid=False)
                    if char.isspace() or char in '._':
                        continue
                    else:
                        break
            # Check the name doesn't end mid-word (guessit might put the border before or after the space after title)
            if (
                data[title_end - 1].isalnum()
                and len(data) <= title_end
                or not self._is_valid_name(data, guessit_options=guessit_options)
            ):
                valid = False
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
                        valid = False
        else:
            valid = False
        season = guess_result.get('season')
        episode = guess_result.get('episode')
        if episode is None and 'part' in guess_result:
            episode = guess_result['part']
        if isinstance(episode, list):
            # guessit >=2.1.4 returns a list for multi-packs, but we just want the first one and the number of eps
            episode = episode[0]
        date = guess_result.get('date')
        quality = self._quality(guess_result)
        proper_count = self._proper_count(guess_result)
        group = guess_result.get('release_group')
        # Validate group with from_group
        if not self._is_valid_groups(group, guessit_options.get('allow_groups', [])):
            valid = False
        # Validate country, TODO: LEGACY
        if country and name.endswith(')'):
            p_start = name.rfind('(')
            if p_start != -1:
                parenthetical = re.escape(name[p_start + 1 : -1])
                if parenthetical and parenthetical.lower() != str(country).lower():
                    valid = False
        # Check the full list of 'episode_details' for special,
        # since things like 'pilot' and 'unaired' can also show up there
        special = any(
            v.lower() == 'special' for v in guess_result.values_list.get('episode_details', [])
        )
        if 'episode' not in guess_result.values_list:
            episodes = len(guess_result.values_list.get('part', []))
        else:
            episodes = len(guess_result.values_list['episode'])
        if episodes > 3:
            valid = False
        identified_by = kwargs.get('identified_by', 'auto')
        identifier_type, identifier = None, None
        if identified_by in ['date', 'auto']:
            if date:
                identifier_type = 'date'
                identifier = date
        if not identifier_type and identified_by in ['ep', 'auto']:
            if episode is not None:
                if season is None and kwargs.get('allow_seasonless', True):
                    if 'part' in guess_result:
                        season = 1
                    else:
                        episode_raw = guess_result.matches['episode'][0].initiator.raw
                        if episode_raw and any(
                            c.isalpha() and c.lower() != 'v' for c in episode_raw
                        ):
                            season = 1
                if season is not None:
                    identifier_type = 'ep'
                    identifier = (season, episode)

        if not identifier_type and identified_by in ['id', 'auto']:
            if guess_result.matches['regexpId']:
                identifier_type = 'id'
                identifier = '-'.join(match.value for match in guess_result.matches['regexpId'])
        if not identifier_type and identified_by in ['sequence', 'auto']:
            if episode is not None:
                identifier_type = 'sequence'
                identifier = episode
        if (not identifier_type or guessit_options.get('prefer_specials')) and (
            special or guessit_options.get('assume_special')
        ):
            identifier_type = 'special'
            identifier = guess_result.get('episode_title', 'special')
        if not identifier_type:
            valid = False
        # TODO: Legacy - Complete == invalid
        if 'complete' in normalize_component(guess_result.get('other')):
            valid = False

        parsed = SeriesParseResult(
            data=data,
            name=name,
            episodes=episodes,
            identified_by=identified_by,
            id=identifier,
            id_type=identifier_type,
            quality=quality,
            proper_count=proper_count,
            special=special,
            group=group,
            valid=valid,
        )

        log.debug('Parsing result: %s (in %s ms)', parsed, (preferred_clock() - start) * 1000)
        return parsed

    # TODO: The following functions are sort of legacy. No idea if they should be changed.
    def _is_valid_name(self, data, guessit_options):
        if not guessit_options.get('name'):
            return True
        # name end position
        name_end = 0

        # regexp name matching
        re_from_name = False
        name_regexps = ReList(guessit_options.get('name_regexps', []))
        if not name_regexps:
            # if we don't have name_regexps, generate one from the name
            name_regexps = ReList(
                name_to_re(name, default_ignore_prefixes, None)
                for name in [guessit_options['name']] + guessit_options.get('alternate_names', [])
            )
            # With auto regex generation, the first regex group captures the name
            re_from_name = True
        # try all specified regexps on this data
        for name_re in name_regexps:
            match = re.search(name_re, data)
            if match:
                match_end = match.end(1 if re_from_name else 0)
                # Always pick the longest matching regex
                if match_end > name_end:
                    name_end = match_end
                log.debug('NAME SUCCESS: %s matched to %s', name_re.pattern, data)
        if not name_end:
            # leave this invalid
            log.debug(
                'FAIL: name regexps %s do not match %s',
                [regexp.pattern for regexp in name_regexps],
                data,
            )
            return False
        return True

    def _is_valid_groups(self, group, allow_groups):
        if not allow_groups:
            return True
        if not group:
            return False
        normalized_allow_groups = [x.lower() for x in allow_groups]
        # TODO: special case for guessit with expected_group parameter
        if isinstance(group, list):
            return any(g.lower() in normalized_allow_groups for g in group)

        return group.lower() in normalized_allow_groups


@event('plugin.register')
def register_plugin():
    plugin.register(
        ParserGuessit, 'parser_guessit', interfaces=['movie_parser', 'series_parser'], api_ver=2
    )
