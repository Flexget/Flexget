import re
from typing import List, Union
from unicodedata import normalize

import babelfish
from guessit.api import GuessItApi, GuessitException
from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event

PLUGIN_NAME = 'translations'
logger = logger.bind(name=PLUGIN_NAME)

UNKNOWN = 'unknown'  # It's a language but is unknown
DEFAULT = 'default'  # Default when none applies
NATIVE = 'native'  # Native language
NONE = 'none'  # No language
OTHER = 'other'  # It's a valid language, but not matched
ACTION_ACCEPT = 'accept'  # Accept entry
ACTION_REJECT = 'reject'  # Reject entry
ACTION_DO_NOTHING = 'do_nothing'  # Ignore check (internal)

Language = babelfish.Language


class MyCodeConverter(babelfish.LanguageEquivalenceConverter):
    """
    This Class will allow to declare all the match that babelfish is not able to match
    """

    SYMBOLS = {}


babelfish.language_converters['mycode'] = MyCodeConverter()


class Translations:
    """
    Take action on translated content

    Example:

    translations:
      action: reject

    translations:
      languages:
        - "imdb_languages"
        - "trakt_language"
        - "trakt_series_language"
      dubbed: reject

    translations:
      languages_synonyms:
        portuguese:
          - tuga
      languages:
        - "imdb_languages"
        - "trakt_language"
        - "trakt_series_language"
      dubbed:
        portuguese: "accept"
        default: "reject"
      subbed:
        portuguese: "accept"
        default: "reject"
    """

    schema = {
        'oneOf': [
            {'type': 'string', 'enum': [ACTION_ACCEPT, ACTION_REJECT, ACTION_DO_NOTHING]},
            {'type': 'boolean'},
            {
                'type': 'object',
                'additionalProperties': False,
                'properties': {
                    'source': {'type': 'string', 'default': 'title'},
                    'languages': one_or_more({'type': 'string'}),
                    'language_fields': one_or_more({'type': 'string'}),
                    'languages_synonyms': {
                        "type": 'object',
                        'additionalProperties': {
                            'type': 'array',
                            'items': {'type': 'string'},
                            'minItems': 1,
                        },
                    },
                    'dubbed': {
                        'oneOf': [
                            {
                                "type": 'string',
                                'enum': [ACTION_ACCEPT, ACTION_REJECT, ACTION_DO_NOTHING],
                            },
                            {
                                "type": 'object',
                                'properties': {
                                    OTHER: {
                                        'type': 'string',
                                        'enum': [ACTION_ACCEPT, ACTION_REJECT, ACTION_DO_NOTHING],
                                    },
                                    NATIVE: {
                                        'type': 'string',
                                        'enum': [ACTION_ACCEPT, ACTION_REJECT, ACTION_DO_NOTHING],
                                    },
                                    DEFAULT: {
                                        'type': 'string',
                                        'enum': [ACTION_ACCEPT, ACTION_REJECT, ACTION_DO_NOTHING],
                                    },
                                    UNKNOWN: {
                                        'type': 'string',
                                        'enum': [ACTION_ACCEPT, ACTION_REJECT, ACTION_DO_NOTHING],
                                    },
                                },
                                'additionalProperties': {
                                    'type': 'string',
                                    'enum': [ACTION_ACCEPT, ACTION_REJECT, ACTION_DO_NOTHING],
                                },
                            },
                        ]
                    },
                    'subbed': {
                        'oneOf': [
                            {
                                "type": 'string',
                                'enum': [ACTION_ACCEPT, ACTION_REJECT, ACTION_DO_NOTHING],
                            },
                            {
                                "type": 'object',
                                'properties': {
                                    OTHER: {
                                        'type': 'string',
                                        'enum': [ACTION_ACCEPT, ACTION_REJECT, ACTION_DO_NOTHING],
                                    },
                                    NONE: {
                                        'type': 'string',
                                        'enum': [ACTION_ACCEPT, ACTION_REJECT, ACTION_DO_NOTHING],
                                    },
                                    DEFAULT: {
                                        'type': 'string',
                                        'enum': [ACTION_ACCEPT, ACTION_REJECT, ACTION_DO_NOTHING],
                                    },
                                    UNKNOWN: {
                                        'type': 'string',
                                        'enum': [ACTION_ACCEPT, ACTION_REJECT, ACTION_DO_NOTHING],
                                    },
                                },
                                'additionalProperties': {
                                    'type': 'string',
                                    'enum': [ACTION_ACCEPT, ACTION_REJECT, ACTION_DO_NOTHING],
                                },
                            },
                        ]
                    },
                },
            },
        ]
    }

    def clean_symbols(self, text: str) -> str:
        """Replaces common symbols with spaces. Also normalize unicode strings in decomposed form.

        Args:
            text (str): Text to clean

        Returns:
            str: Cleaned text
        """
        result = text
        if isinstance(result, str):
            result = normalize('NFKD', result)
        result = re.sub(r'[ \(\)\-_\[\]\.]+', ' ', result).lower()

        # Leftovers
        result = re.sub(r"[^a-zA-Z0-9 ]", "", result)

        return result

    def _is_language(self, lang: Union[str, Language]) -> bool:
        """Checks if is a valid language

        Args:
            lang (Union[str, Language]): Language to check

        Returns:
            bool: is language
        """

        if isinstance(lang, Language):
            return True

        if not isinstance(lang, str) or lang in ['', 'und', UNKNOWN, NATIVE, DEFAULT, NONE, OTHER]:
            return False

        try:
            mycode = Language.frommycode(lang)
            if mycode:
                lang = mycode.name
        except babelfish.LanguageReverseError:
            logger.debug('`{}` is not a language', lang)
            pass

        try:
            language = Language.fromietf(lang)
        except (ValueError, babelfish.LanguageReverseError):
            try:
                language = Language.fromcode(lang, 'name')
            except ValueError:
                return False
            except babelfish.LanguageReverseError:
                return False

        if isinstance(language, Language):
            return True

        return False

    def _get_language(self, lang: Union[str, List[str], Language, List[Language]]) -> List[str]:
        """Returns the language in text format

        Args:
            lang (Union[str, Language]): Language to return

        Returns:
            str: Language text
        """

        if not isinstance(lang, list):
            languages = [lang]
        else:
            languages = lang

        for key, lang in enumerate(languages):
            if isinstance(lang, Language):
                lang = lang.name

            if not isinstance(lang, str) or lang in ['', 'und', UNKNOWN]:
                languages[key] = UNKNOWN
                continue

            if lang is None or lang == NONE:
                languages[key] = NONE
                continue

            if lang in [NATIVE, DEFAULT, OTHER]:
                languages[key] = lang
                continue

            try:
                mycode = Language.frommycode(lang)
                if mycode:
                    lang = mycode.name
            except babelfish.LanguageReverseError:
                pass

            try:
                language = Language.fromietf(lang)
            except (ValueError, babelfish.LanguageReverseError):
                try:
                    language = Language.fromcode(lang, 'name')
                except ValueError:
                    language = lang
                except babelfish.LanguageReverseError:
                    language = lang

            if isinstance(language, Language):
                language = language.name

            languages[key] = language.lower()

        return languages

    def _process_config(self, config: dict) -> dict:
        """Processes Config to plugin standard

        Args:
            config (dict): Config

        Raises:
            plugin.PluginError: Plugin Error

        Returns:
            dict: Sanitized config
        """

        _config = {}

        # Simple Actions
        if isinstance(config, bool):
            config = ACTION_ACCEPT if config else ACTION_REJECT

        if isinstance(config, str):
            config = {'dubbed': config, 'subbed': config}

        # Source of the filed to parse
        _config['source'] = config.get('source', 'title')

        # The Languages synonums
        _languages_synonyms = config.get('languages_synonyms', [])
        _config['languages_synonyms'] = {}
        for lang in _languages_synonyms:
            if not self._is_language(lang):
                raise plugin.PluginError(f'`{lang}` in languages_synonyms is not a valid language')
            lang = self._get_language(lang)
            language = Language.fromcode(lang[0], 'name')
            _config['languages_synonyms'][language.alpha3] = _languages_synonyms[lang[0]]
            MyCodeConverter.SYMBOLS[language.alpha3] = _languages_synonyms[lang[0]]

        # fields to get the language
        _config['language_fields'] = config.get('language_fields', [])
        if not isinstance(_config['language_fields'], list):
            _config['language_fields'] = [_config['language_fields']]
        elif not _config['language_fields']:
            _config['language_fields'] = []

        # The actual language of the content
        _config['languages'] = config.get('languages', [])
        if not isinstance(_config['languages'], list):
            _config['languages'] = [_config['languages']]
        elif not _config['languages'] and not _config['language_fields']:
            _config['languages'] = [UNKNOWN]

        # Actions to dubbed
        _dubbed = config.get('dubbed', ACTION_DO_NOTHING)
        if isinstance(_dubbed, str):
            if _dubbed in [ACTION_DO_NOTHING]:
                _dubbed = {DEFAULT: _dubbed, NATIVE: _dubbed, UNKNOWN: _dubbed}
            else:
                _dubbed = {
                    DEFAULT: ACTION_DO_NOTHING,
                    OTHER: _dubbed,
                    NATIVE: ACTION_DO_NOTHING,
                    UNKNOWN: _dubbed,
                }

        _config['dubbed'] = {}
        for key in _dubbed:
            key = key.lower()
            if key not in [UNKNOWN, DEFAULT, NATIVE, OTHER] and not self._is_language(key):
                raise plugin.PluginError(f'`{key}` in dubbed is not a valid language for dubbed')

            lang = self._get_language(key)
            _config['dubbed'][lang[0]] = _dubbed[key]

        # Subbed traslations
        _subbed = config.get('subbed', ACTION_DO_NOTHING)
        if isinstance(_subbed, str):
            if _subbed in [ACTION_DO_NOTHING]:
                _subbed = {DEFAULT: _subbed, UNKNOWN: _subbed, NONE: _subbed}
            else:
                _subbed = {
                    DEFAULT: ACTION_DO_NOTHING,
                    OTHER: _subbed,
                    NONE: ACTION_DO_NOTHING,
                    UNKNOWN: _subbed,
                }

        _config['subbed'] = {}
        for key in _subbed:
            key = key.lower()
            if key not in [UNKNOWN, DEFAULT, NONE, OTHER] and not self._is_language(key):
                raise plugin.PluginError(f'`{key}` in subbed is not a valid language for subbed')

            lang = self._get_language(key)
            _config['subbed'][lang[0]] = _subbed[key]

        ## Dubbed default
        for field in [UNKNOWN, DEFAULT, NATIVE, OTHER]:
            if field not in _config['dubbed']:
                _config['dubbed'][field] = _config['dubbed'].get(DEFAULT, ACTION_DO_NOTHING)

        ## Subbed default
        for field in [UNKNOWN, DEFAULT, NONE, OTHER]:
            if field not in _config['subbed']:
                _config['subbed'][field] = _config['subbed'].get(DEFAULT, ACTION_DO_NOTHING)

        return _config

    def _language_to_action(
        self, languages: List[str], stream_languages: List[str], config: dict
    ) -> str:
        """Gets the action to preform to a given language

        Args:
            lang (str): Language to process
            stream_languages (List[str]): List of the streamed languages for the media
            config (dict): Plugin config

        Returns:
            str: Action to preform
        """

        if not stream_languages:
            stream_languages = []

        if NATIVE in languages:
            for stream_language in stream_languages:
                if not self._is_language(stream_language):
                    continue

                if stream_language in config:
                    return config.get(stream_language), stream_language

        final_action = {}

        for lang in languages:
            if config.get(lang) and config[lang] != ACTION_DO_NOTHING:
                final_action[config.get(lang)] = config[lang], lang
                continue

            if lang in stream_languages:
                lang = NATIVE

            action = config.get(lang, None)
            if not action and self._is_language(lang):
                # If it's a language and not defined, use OTHER config
                action = config.get(OTHER, None)

            if action:
                final_action[action] = action, lang
                continue

            if self._is_language(lang):
                action = config.get(OTHER, None)

        # Handle Dual Language Files TODO: Add multi language exeption?
        if ACTION_ACCEPT in final_action:
            return final_action[ACTION_ACCEPT]
        elif ACTION_DO_NOTHING in final_action:
            return final_action[ACTION_DO_NOTHING]
        elif ACTION_REJECT in final_action:
            return final_action[ACTION_REJECT]

        return config.get(DEFAULT, ACTION_DO_NOTHING), languages

    def on_task_filter(self, task, config):
        guessit_api = GuessItApi()
        guessit_api.config = {}
        guessit_api.config['synonyms'] = {'nordic': ['nordic']}

        my_config = self._process_config(config)

        synonyms = {}
        for synonym in my_config['languages_synonyms']:
            synonyms[synonym] = my_config['languages_synonyms'][synonym]

        for entry in task.entries:
            guess = {}

            source = my_config['source']

            if my_config['source'] not in entry:
                raise plugin.PluginError(f'No field {source} in entry')

            title = entry.get(my_config['source'])
            title_clean = self.clean_symbols(title)
            real_title = title

            if entry.get('series_name'):
                real_title = entry['series_name']
                guess['type'] = 'episode'
                guess['expected_title'] = [self.clean_symbols(real_title)]
            elif entry.get('movie_name'):
                real_title = entry['movie_name']
                guess['type'] = 'movie'
                guess['expected_title'] = [self.clean_symbols(real_title)]

            if 'alternate_names' in entry:
                guess['expected_title'] = [
                    self.clean_symbols(name) for name in entry['alternate_names']
                ]

            guess['single_value'] = False
            guess['advanced_config'] = {'language': {'synonyms': synonyms}}

            try:
                guess_result = guessit_api.guessit(title_clean, options=guess)
            except GuessitException as e:
                logger.warning('Parsing `{}` with guessit failed: {}', title_clean, e)
                continue

            if 'language' in guess_result:
                file_language = self._get_language(guess_result.get('language'))
                logger.debug('`{}` is in language `{}`', title, file_language)
            else:
                file_language = [NATIVE]
                logger.debug('`{}` is assumed not dubbed', title)

            if 'subtitle_language' in guess_result:
                file_subtitles = self._get_language(guess_result.get('subtitle_language'))
                logger.debug('`{}` is in language `{}`', title, file_subtitles)
            else:
                file_subtitles = [NONE]
                logger.debug('`{}` is assumed not subbed', title)

            stream_languages = {}
            for lang in my_config['languages']:
                if self._is_language(lang):
                    logger.debug('Using `{}` as native language for {}', lang, real_title)
                    language = self._get_language(lang)
                    if language[0] not in stream_languages:
                        stream_languages[language[0]] = 0

                    stream_languages[language[0]] += 1
                    continue

                if lang == UNKNOWN:
                    if UNKNOWN not in stream_languages:
                        stream_languages[UNKNOWN] = 1
                    continue

            for source in my_config['language_fields']:
                if source not in entry:
                    logger.warning('Entry does not contain a field called `{}`', source)
                    continue

                languages = entry.get(source)
                if not isinstance(languages, list):
                    languages = [languages]

                for lang in languages:
                    if not lang:
                        continue

                    language = self._get_language(lang)

                    if language[0] not in stream_languages:
                        stream_languages[language[0]] = 0

                    stream_languages[language[0]] += 1

            if not stream_languages:
                stream_languages[UNKNOWN] = 1

            stream_languages = sorted(
                stream_languages.items(), key=lambda item: item[1], reverse=True
            )

            # Detect Main Language (If more than one source select the main one)
            main_language = stream_languages[0]
            stream_languages = [(lan[0]) for lan in stream_languages if lan[1] >= main_language[1]]

            logger.debug('Processing `{}` with native language `{}`', real_title, stream_languages)

            # Check Dubbed
            action, f_language = self._language_to_action(
                file_language, stream_languages, my_config['dubbed']
            )

            accept = ''
            reject = ''
            nothing = ''

            if action == ACTION_DO_NOTHING:
                logger.debug(
                    'Skiping dubbed check on `{}` because is in language is `{}`',
                    title,
                    f_language,
                )
            elif action == ACTION_REJECT:
                reject = f'`{title}` is `{f_language}` language'
            elif action == ACTION_ACCEPT:
                accept = f'`{title}` is `{f_language}` language'

            # Check Subbed
            action, f_subtitles = self._language_to_action(
                file_subtitles, None, my_config['subbed']
            )

            if action == ACTION_DO_NOTHING:
                if NONE not in f_subtitles:
                    logger.debug(
                        'Skiping subbed check on `{}` because is subbed in `{}`',
                        title,
                        f_subtitles,
                    )
            elif action == ACTION_REJECT:
                if reject:
                    reject += ' and '
                reject += f'`{title}` is `{f_subtitles}` subbed'
            elif action == ACTION_ACCEPT:
                if accept:
                    accept += ' and '
                accept += f'`{title}` is `{f_subtitles}` subbed'

            if reject:
                entry.reject(reject)
            elif accept:
                entry.accept(accept)
            elif nothing:
                logger.debug(nothing)


@event('plugin.register')
def register_plugin():
    plugin.register(Translations, PLUGIN_NAME, api_ver=2)
