import guessit

from .parser_common import PARSER_EPISODE, PARSER_MOVIE, PARSER_VIDEO
from .parser_common import ParsedEntry, ParsedVideoQuality, ParsedVideo, ParsedSerie, ParsedMovie, Parser

guessit.default_options = {'name_only': True}

class GuessitParsedEntry(ParsedEntry):
    def __init__(self, raw, guess_result):
        ParsedEntry.__init__(self, raw)
        self._guess_result = guess_result

    @property
    def release_group(self):
        return self._guess_result.get('releaseGroup')

    @property
    def proper(self):
        return 'Proper' in self._guess_result.get('other', {})

    @property
    def date(self):
        return self._guess_result.get('date')

    @property
    def properties(self):
        self._guess_result


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
    def is_screener(self):
        return 'Screener' in self._guess_result.get('other', {})

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


class GuessitParsedVideo(GuessitParsedEntry, ParsedVideo):
    def __init__(self, raw, guess_result):
        GuessitParsedEntry.__init__(self, raw, guess_result)
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
    def __init__(self, raw, guess_result):
        GuessitParsedVideo.__init__(self, raw, guess_result)

    @property
    def title(self):
        return self._guess_result.get('title')


class GuessitParsedSerie(GuessitParsedVideo, ParsedSerie):
    def __init__(self, raw, guess_result):
        GuessitParsedVideo.__init__(self, raw, guess_result)

    @property
    def series(self):
        return self._guess_result.get('series')

    @property
    def title(self):
        self._guess_result.get('title')

    @property
    def episode_details(self):
        return self._guess_result.get('episodeDetails')

    @property
    def episode(self):
        return self._guess_result.get('episodeNumber')

    @property
    def episodes(self):
        return len(self._guess_result.get('episodeList', filter(None, [self.episode])))

    @property
    def season(self):
        return self._guess_result.get('season')


class GuessitParser(Parser):
    def __init__(self):
        self._type_map = {PARSER_EPISODE: 'episode', PARSER_VIDEO: 'video', PARSER_MOVIE: 'movie'}

    def parse(self, input_, type_=None, attended_name=None, **kwargs):
        type_ = self._type_map.get(type_)

        options = self._filter_options(kwargs)

        guess_result = guessit.guess_file_info(input_, options=options, type=type_)

        type_ = guess_result.get('type', type_)
        if (type_ == 'episode'):
            return GuessitParsedSerie(input_, guess_result)
        elif (type_ == 'movie'):
            return GuessitParsedMovie(input_, guess_result)
        elif (type_ == 'video'):
            return GuessitParsedVideo
        else:
            return GuessitParsedEntry(input_, guess_result)

    def _filter_options(self, options):
        return options
