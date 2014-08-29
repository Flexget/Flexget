import guessit

from .parser_common import PARSER_EPISODE, PARSER_MOVIE, PARSER_VIDEO, remove_dirt
from .parser_common import ParsedEntry, ParsedVideoQuality, ParsedVideo, ParsedSerie, ParsedMovie, Parser

from copy import deepcopy

import re
from string import capwords


def clean_value(name):
    # Move anything in leading brackets to the end
    #name = re.sub(r'^\[(.*?)\](.*)', r'\2 \1', name)

    for char in '[]()_,.':
        name = name.replace(char, ' ')

    # if there are no spaces
    if name.find(' ') == -1:
        name = name.replace('-', ' ')

    # remove unwanted words (imax, ..)
    #self.remove_words(data, self.remove)

    #MovieParser.strip_spaces
    name = ' '.join(name.split())
    return name

guessit.default_options = {'name_only': True, 'clean_function': clean_value, 'allowed_languages': ['en', 'fr'], 'allowed_countries': ['us', 'uk']}


class GuessitParsedEntry(ParsedEntry):
    def __init__(self, raw, name, guess_result):
        ParsedEntry.__init__(self, raw, name)
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
    def __init__(self, raw, name, guess_result):
        GuessitParsedEntry.__init__(self, raw, name, guess_result)
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
    def __init__(self, raw, name, guess_result):
        GuessitParsedVideo.__init__(self, raw, name, guess_result)

    @property
    def title(self):
        return self._guess_result.get('title')


class GuessitParsedSerie(GuessitParsedVideo, ParsedSerie):
    def __init__(self, raw, name, guess_result):
        GuessitParsedVideo.__init__(self, raw, name, guess_result)

    @property
    def parsed_name(self):
        parsed_name = super(GuessitParsedVideo, self).parsed_name
        if self.year and self._guess_result.span('year')[0] - 1 == self._guess_result.span('series')[1]:
            parsed_name = parsed_name + ' ' + self.year
        return parsed_name

    @property
    def series(self):
        return self._guess_result.get('series')

    @property
    def title(self):
        return self._guess_result.get('title')

    @property
    def is_special(self):
        return self.episode_details and len(self.episode_details) > 0

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

    def build_parsed(self, guess_result, input_, type_=None, name=None, **kwargs):
        type_ = guess_result.get('type', type_)
        if (type_ == 'episode'):
            return GuessitParsedSerie(input_, name, guess_result)
        elif (type_ == 'movie'):
            return GuessitParsedMovie(input_, name, guess_result)
        elif (type_ == 'video'):
            return GuessitParsedVideo(input_, name, guess_result)
        else:
            return GuessitParsedEntry(input_, name, guess_result)

    def clean_input_name(self, name):
        name = re.sub('[_.,\[\]\(\):]', ' ', name)
        # Remove possible episode title from series name (anything after a ' - ')
        name = name.split(' - ')[0]
        # Replace some special characters with spaces
        name = re.sub('[\._\(\) ]+', ' ', name).strip(' -')
        # Normalize capitalization to title case
        name = capwords(name)
        return name

    def parse(self, input_, type_=None, name=None, **kwargs):
        type_ = self._type_map.get(type_)

        options = self._filter_options(kwargs)

        guess_result = guessit.guess_file_info(input_, options=options, type=type_)
        if name and name != input_ and not type_:
            # Metainfo, we don't know if we have have a serie.
            # Grabbing serie name.
            name = self.clean_input_name(name)
            name_options = deepcopy(options)
            name_options['disabled_transformers'] = ['GuessWeakEpisodesRexps', 'GuessYear', 'GuessCountry']
            name_guess_result = guessit.guess_file_info(name, options=name_options, type=type_)
            name = self.build_parsed(name_guess_result, name, options=name_options, type=type_, **kwargs).name

        return self.build_parsed(guess_result, input_, options=options, type=type_, name=(name if name != input_ else None), **kwargs)

    def _filter_options(self, options):
        identified_by = options.get('identified_by')
        if identified_by in ['ep']:
            options['episode_prefer_number'] = False
        else:
            options['episode_prefer_number'] = True
        return options
