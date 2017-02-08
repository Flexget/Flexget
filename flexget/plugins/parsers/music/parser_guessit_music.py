from __future__ import unicode_literals, division, absolute_import
import time
from flexget import plugin
from flexget.event import event
from flexget.plugins.parsers.parser_common import ParsedAudio, ParsedAudioQuality, ParsedEntry, ParsedTitledAudio

from pkg_resources import EntryPoint
from guessit.textutils import normalize_unicode, clean_default
from guessit.matchtree import MatchTree
from guessit.plugins.transformers import CustomTransformerExtensionManager
import logging

log = logging.getLogger('parser_guessit_music')
# Guessit debug log is a bit too verbose
logging.getLogger('guessit').setLevel(logging.INFO)


class GuessitParsedAudio(ParsedAudio):
    def __init__(self, data, name, guess_result, **kwargs):
        ParsedAudio.__init__(self, data, name, **kwargs)
        self._quality = None
        self._guess_result = guess_result

    @property
    def quality(self):
        if self._quality is None:
            self._quality = GuessitParsedAudioQuality(self._guess_result)
        return self._quality

    @property
    def year(self):
        return self._guess_result.get('year')

    @property
    def properties(self):
        return self._guess_result

    @property
    def parsed_group(self):
        return self._guess_result.get('releaseGroup')


class GuessitParsedAudioQuality(ParsedAudioQuality):
    def __init__(self, guess_result):
        self._guess_result = guess_result

    @property
    def source(self):
        return self._guess_result.get('source')

    @property
    def audio_codec(self):
        return self._guess_result.get('audioCodec')

    @property
    def audio_profile(self):
        return self._guess_result.get('audioProfile')

    @property
    def audio_sampling(self):
        return self._guess_result.get('audioSampling')

    @property
    def audio_bit_depth(self):
        return self._guess_result.get('audioBitDepth')

    @property
    def audio_bit_rate(self):
        return self._guess_result.get('audioBitRate')

    @property
    def audio_bit_rate_distribution(self):
        return self._guess_result.get('audioBitRateDistribution')

    @property
    def audio_channels(self):
        return self._guess_result.get('audioChannels')


class GuessitParsedTitledAudio(GuessitParsedAudio, ParsedTitledAudio):
    def __init__(self, data, name, guess_result, **kwargs):
        ParsedTitledAudio.__init__(self);
        GuessitParsedAudio.__init__(self, data, name, guess_result, **kwargs)

    @property
    def artist(self):
        return self._guess_result.get('artist')

    @property
    def title(self):
        return self._guess_result.get('title')

    @property
    def parsed_type(self):
        # TODO: parsed_type = self._guess_result.get('type', self.type)
        if self.artist and self.title:
            return self.type
        else:
            return None


class ParserGuessitMusic(object):
    """
    Music parser use GuessIt. It's like IterativeMatcher but
    it use others Transformers (for music tag matching).

    :type self.transformers: list[guessit.transformers.Transformer]
    """
    def __init__(self):
        transfo_manager = MusicTransformerExtensionManager()
        self.transformers = transfo_manager.objects()

    def _guessit_options(self, options):
        settings = {'clean_function': clean_default}
        settings.update(options)
        return settings

    @staticmethod
    def prepare_unicode(entry_name):
        if not isinstance(entry_name, unicode):
            entry_name = entry_name.decode('utf-8')
        return normalize_unicode(entry_name)

    def parse(self, data, **kwargs):
        options = self._guessit_options(kwargs)
        data = ParserGuessitMusic.prepare_unicode(data)
        match_tree = MatchTree(data, clean_function=options['clean_function'])
        for a_transformer in self.transformers:
            a_transformer.process(match_tree, options)
        for a_transformer in self.transformers:
            a_transformer.post_process(match_tree, options)

        return match_tree

    def parse_music(self, data, **kwargs):
        log.debug('Parsing music entry: `%s` [options: %s]', data, kwargs)
        start = time.clock()
        guess_result = self.parse(data, **kwargs).matched()
        parsed = GuessitParsedTitledAudio(data, kwargs.pop('name', None), guess_result, **kwargs)
        end = time.clock()
        log.debug('Parsing result: %s (in %s ms)', parsed, (end - start) * 1000)
        return parsed

    @staticmethod
    # TODO: Manage quality properties
    def get_entry_map():
        return {
            'music_artist': 'artist',
            'music_title': 'title',
            'year': 'year',
            'quality': 'quality'
        }


class MusicTransformerExtensionManager(CustomTransformerExtensionManager):
    @property
    def _internal_entry_points(self):
        return [
            'split_explicit_groups = flexget.plugins.parsers.music.split_explicit_groups:SplitExplicitGroups',
            'guess_date = guessit.transfo.guess_date:GuessDate',
            'guess_website = guessit.transfo.guess_website:GuessWebsite',
            'guess_properties = flexget.plugins.parsers.music.guess_properties:GuessProperties',
            'guess_bitrate = flexget.plugins.parsers.music.guess_bitrate:GuessBitrate',
            'guess_year = guessit.transfo.guess_year:GuessYear',
            'guess_country = guessit.transfo.guess_country:GuessCountry',
            'guess_idnumber = guessit.transfo.guess_idnumber:GuessIdnumber',
            'expected_title = guessit.transfo.expected_title:ExpectedTitle'
            'guess_title_artist = flexget.plugins.parsers.music.guess_title_artist:GuessMusicArtistAndTitle'
        ]

    def _find_entry_points(self, namespace):
        entry_points = {}
        # Internal entry points
        if namespace == self.namespace:
            for internal_entry_point_str in self._internal_entry_points:
                internal_entry_point = EntryPoint.parse(internal_entry_point_str)
                entry_points[internal_entry_point.name] = internal_entry_point

        # Package entry points
        setuptools_entrypoints = super(MusicTransformerExtensionManager, self)._find_entry_points(namespace)
        for setuptools_entrypoint in setuptools_entrypoints:
            entry_points[setuptools_entrypoint.name] = setuptools_entrypoint

        return list(entry_points.values())


@event('plugin.register')
def register_plugin():
    plugin.register(ParserGuessitMusic, 'parser_guessit_music', groups=['music_parser'], api_ver=2)
