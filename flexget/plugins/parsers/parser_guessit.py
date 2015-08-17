from __future__ import unicode_literals, division, absolute_import

import datetime
import logging
import re
import time

import guessit
from guessit.containers import PropertiesContainer, NoValidator
from guessit.matcher import GuessFinder
from guessit.plugins.transformers import Transformer, add_transformer

from flexget import plugin
from flexget.event import event
from flexget.utils import qualities
from .parser_common import clean_value, old_assume_quality
from .parser_common import ParsedEntry, ParsedVideoQuality, ParsedVideo, ParsedSerie, ParsedMovie


log = logging.getLogger('parser_guessit')
# Guessit debug log is a bit too verbose
logging.getLogger('guessit').setLevel(logging.INFO)


class GuessRegexpId(Transformer):
    def __init__(self):
        Transformer.__init__(self, 21)

    def supported_properties(self):
        return ['regexpId']

    def guess_regexps_id(self, string, node=None, options=None):
        container = PropertiesContainer(enhance=False, canonical_from_pattern=False)
        for regexp in options.get("id_regexps"):
            container.register_property('regexpId', regexp, confidence=1.0, validator=NoValidator())
        found = container.find_properties(string, node, options)
        return container.as_guess(found, string)

    def should_process(self, mtree, options=None):
        return options and options.get("id_regexps")

    def process(self, mtree, options=None):
        GuessFinder(self.guess_regexps_id, None, self.log, options).process_nodes(mtree.unidentified_leaves())


add_transformer('guess_regexp_id = flexget.plugins.parsers.parser_guessit:GuessRegexpId')


class GuessitParsedEntry(ParsedEntry):
    def __init__(self, data, name, guess_result, **kwargs):
        ParsedEntry.__init__(self, data, name, **kwargs)
        self._guess_result = guess_result

    @property
    def parsed_group(self):
        return self._guess_result.get('releaseGroup')

    @property
    def parsed_type(self):
        parsed_type = self._guess_result.get('type', self.type)
        if parsed_type == 'episode':
            return 'series'
        return parsed_type

    @property
    def proper_count(self):
        # todo: deprecated. We should remove this field from the rest of code.
        version = self._guess_result.get('version')
        if version is None:
            version = 0
        elif version <= 0:
            version = -1
        else:
            version = version - 1
        proper_count = self._guess_result.get('properCount', 0)
        fastsub = 'Fastsub' in self._guess_result.get('other', [])
        return version + proper_count - (5 if fastsub else 0)

    @property
    def properties(self):
        return self._guess_result


class GuessitParsedVideoQuality(ParsedVideoQuality):
    def __init__(self, guess_result):
        self._guess_result = guess_result

    @property
    def video_codec(self):
        return self._guess_result.get('videoCodec')

    @property
    def source(self):
        return self._guess_result.get('source')

    @property
    def format(self):
        return self._guess_result.get('format')

    @property
    def audio_codec(self):
        return self._guess_result.get('audioCodec')

    @property
    def video_profile(self):
        return self._guess_result.get('videoProfile')

    @property
    def screen_size(self):
        return self._guess_result.get('screenSize')

    @property
    def audio_channels(self):
        return self._guess_result.get('audioChannels')

    @property
    def audio_profile(self):
        return self._guess_result.get('audioProfile')

    @property
    def old_resolution(self):
        return self.screen_size if self.screen_size else 'HR' if 'HR' in self._guess_result.get('other', []) else None

    @property
    def old_source(self):
        """
        Those properties should really be extracted to another category of quality ...
        """
        if 'Screener' in self._guess_result.get('other', {}):
            if self.format == 'BluRay':
                return 'bdscr'
            return 'dvdscr'
        if 'Preair' in self._guess_result.get('other', {}):
            return 'preair'
        if 'R5' in self._guess_result.get('other', {}):
            return 'r5'
        return self.format.replace('-', '') if self.format else None

    @property
    def old_codec(self):
        if self.video_profile == '10bit':
            return '10bit'
        return self.video_codec

    @property
    def old_audio(self):
        if self.audio_codec == 'DTS' and (self.audio_profile in ['HD', 'HDMA']):
            return 'dtshd'
        elif self.audio_channels == '5.1' and self.audio_codec is None or self.audio_codec == 'DolbyDigital':
            return 'dd5.1'
        return self.audio_codec

    def to_old_quality(self, assumed_quality=None):
        resolution = self.old_resolution
        source = self.old_source
        codec = self.old_codec
        audio = self.old_audio

        old_quality = qualities.Quality(' '.join(filter(None, [resolution, source, codec, audio])))
        old_quality = old_assume_quality(old_quality, assumed_quality)

        return old_quality


class GuessitParsedVideo(GuessitParsedEntry, ParsedVideo):
    def __init__(self, data, name, guess_result, **kwargs):
        GuessitParsedEntry.__init__(self, data, name, guess_result, **kwargs)
        self._quality = None

    @property
    def is_3d(self):
        return '3D' in self._guess_result.get('other', {})

    @property
    def quality2(self):
        if self._quality is None:
            self._quality = GuessitParsedVideoQuality(self._guess_result)
        return self._quality

    @property
    def subtitle_languages(self):
        return self._guess_result.get('subtitleLanguage')

    @property
    def languages(self):
        return self._guess_result.get('Language')

    @property
    def year(self):
        return self._guess_result.get('year')


class GuessitParsedMovie(GuessitParsedVideo, ParsedMovie):
    def __init__(self, data, name, guess_result, **kwargs):
        GuessitParsedVideo.__init__(self, data, name, guess_result, **kwargs)

    @property
    def title(self):
        return self._guess_result.get('title')


class GuessitParsedSerie(GuessitParsedVideo, ParsedSerie):
    part_re = re.compile('part\\s?(\\d+)', re.IGNORECASE)

    def __init__(self, data, name, guess_result, **kwargs):
        GuessitParsedVideo.__init__(self, data, name, guess_result, **kwargs)

    @property
    def series(self):
        return self._guess_result.get('series')

    @property
    def country(self):
        return str(self._guess_result.get('country')) if 'country' in self._guess_result else None

    @property
    def complete(self):
        return 'Complete' in self._guess_result.get('other', [])

    @property
    def regexp_id(self):
        regexp_id = self._guess_result.get('regexpId')
        if isinstance(regexp_id, list):
            return '-'.join(regexp_id)
        else:
            return regexp_id

    @property
    def title(self):
        return self._guess_result.get('title')

    @property
    def special(self):
        return (self.episode_details and len(self.episode_details) > 0 or
                (self.title and self.title.lower().strip() == 'special'))

    @property
    def episode_details(self):
        return self._guess_result.get('episodeDetails')

    @property
    def episode(self):
        episode = self._guess_result.get('episodeNumber')
        if episode is None and 'part' in self._guess_result and not self.date:
            return self._guess_result.get('part')
        if episode is None and self.title:
            matched = self.part_re.search(self.title)
            if matched:
                return int(matched.group(1))
        return episode

    @property
    def episodes(self):
        return len(self._guess_result.get('episodeList', filter(lambda x: x is not None, [self.episode])))

    @property
    def date(self):
        d = self._guess_result.get('date')
        if d:
            if d > datetime.date.today() + datetime.timedelta(days=1):
                return None
            # Don't accept dates that are too old
            if d < datetime.date(1970, 1, 1):
                return None
            return d

    @property
    def parsed_season(self):
        season = self._guess_result.get('season')
        if season is None and self.episode and not self.allow_seasonless:
            if 'part' in self._guess_result:
                return 1
            episode_raw = self._guess_result.metadata('episodeNumber').raw
            if episode_raw and any(c.isalpha() and c.lower() != 'v' for c in episode_raw):
                return 1
        return season

    @property
    def valid_strict(self):
        return True


class ParserGuessit(object):
    def _guessit_options(self, options):
        settings = {'name_only': True, 'clean_function': clean_value, 'allowed_languages': ['en', 'fr'],
                    'allowed_countries': ['us', 'uk', 'gb']}
        options['episode_prefer_number'] = not options.get('identified_by') == 'ep'
        if options.get('allow_groups'):
            options['expected_group'] = options['allow_groups']
        if 'date_yearfirst' in options:
            options['date_year_first'] = options['date_yearfirst']
        if 'date_dayfirst' in options:
            options['date_day_first'] = options['date_dayfirst']
        settings.update(options)
        return settings

    # movie_parser API
    def parse_movie(self, data, **kwargs):
        log.debug('Parsing movie: `%s` [options: %s]', data, kwargs)
        start = time.clock()
        guessit_options = self._guessit_options(kwargs)
        guess_result = guessit.guess_file_info(data, options=guessit_options, type='movie')
        parsed = GuessitParsedMovie(data, kwargs.pop('name', None), guess_result, **kwargs)
        end = time.clock()
        log.debug('Parsing result: %s (in %s ms)', parsed, (end - start) * 1000)
        return parsed

    # series_parser API
    def parse_series(self, data, **kwargs):
        log.debug('Parsing series: `%s` [options: %s]', data, kwargs)
        guessit_options = self._guessit_options(kwargs)
        if kwargs.get('name') and not guessit_options.get('strict_name'):
            guessit_options['expected_series'] = [kwargs['name']]
        start = time.clock()
        # If no series name is provided, we don't tell guessit what kind of match we are looking for
        # This prevents guessit from determining that too general of matches are series
        parse_type = 'episode' if kwargs.get('name') else None
        guess_result = guessit.guess_file_info(data, options=guessit_options, type=parse_type)
        if guess_result.get('type') != 'episode':
            # TODO: All other failures return an invalid parser. This is just a hack to match. Maybe exception instead?
            class InvalidParser(object):
                valid = False
            return InvalidParser()
        parsed = GuessitParsedSerie(data, kwargs.pop('name', None), guess_result, **kwargs)
        end = time.clock()
        log.debug('Parsing result: %s (in %s ms)', parsed, (end - start) * 1000)
        return parsed


@event('plugin.register')
def register_plugin():
    plugin.register(ParserGuessit, 'parser_guessit', groups=['movie_parser', 'series_parser'], api_ver=2)
