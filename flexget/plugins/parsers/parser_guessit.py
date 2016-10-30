from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from future.utils import native

import logging
import sys
import time

from guessit.rules import rebulk_builder
from guessit.api import GuessItApi
from rebulk import Rebulk
from rebulk.pattern import RePattern

from flexget import plugin
from flexget.event import event
from flexget.utils import qualities
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
        guess_result = guessit_api.guessit(native(data), options=guessit_options)
        if guess_result.get('type') != 'episode':
            return SeriesParseResult(data=data, valid=False)

        name = kwargs.get('name')
        if not name:
            name = guess_result.get('title')
            if guess_result.get('country') and hasattr(guess_result.get('country'), 'alpha2'):
                name += ' (%s)' % guess_result.get('country').alpha2
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
            if data[title_end - 1].isalnum() and len(data) <= title_end or data[title_end].isalnum():
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
        if not id_type and special:
            id_type = 'special'
            id = guess_result.get('title', 'special')
        if not id_type:
            return SeriesParseResult(data=data, valid=False)

        parsed = SeriesParseResult(
            data=data,
            name=name,
            episodes=episodes,
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


@event('plugin.register')
def register_plugin():
    plugin.register(ParserGuessit, 'parser_guessit', groups=['movie_parser', 'series_parser'], api_ver=2)
