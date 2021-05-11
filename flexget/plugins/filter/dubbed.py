import re
from unicodedata import normalize
from typing import Union, List

from guessit.api import GuessItApi, GuessitException
from loguru import logger
import babelfish

from flexget import plugin
from flexget.event import event
from flexget.config_schema import one_or_more

PLUGIN_NAME = 'dubbed'
logger = logger.bind(name=PLUGIN_NAME)

UNKNOWN = 'unknown'
DEFAULT = 'default'
NATIVE = 'native'
ACTION_ACCEPT = 'accept'
ACTION_REJECT = 'reject'
ACTION_SKIP = 'do_nothing'

Language = babelfish.Language


class MyCodeConverter(babelfish.LanguageEquivalenceConverter):
    """
    This Class will allow to declare all the match that babelfish is not able to match
    """

    SYMBOLS = {}


babelfish.language_converters['mycode'] = MyCodeConverter()


class Dubbed:
    """
    Take action on dubbed content

    Example::

    dubbed:
      action: reject

    dubbed:
      languages:
        - "imdb_languages"
        - "trakt_language"
        - "trakt_series_language"
      action: reject

    dubbed:
      languages_synonyms:
        portuguese:
          - tuga
      languages:
        - "imdb_languages"
        - "trakt_language"
        - "trakt_series_language"
      action:
        portuguese: "accept"
        default: "reject"
    """

    schema = {
        'type': 'object',
        'additionalProperties': False,
        'properties': {
            'source': {'type': 'string', 'default': 'title'},
            'languages': one_or_more({'type': 'string'}),
            'languages_synonyms': {
                "type": 'object',
                'additionalProperties': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'minItems': 1,
                },
            },
            'action': {
                'oneOf': [
                    {"type": 'string', 'enum': [ACTION_ACCEPT, ACTION_REJECT]},
                    {
                        "type": 'object',
                        'properties': {
                            'native': {
                                'type': 'string',
                                'enum': [ACTION_ACCEPT, ACTION_REJECT, ACTION_SKIP],
                                'default': ACTION_REJECT,
                            },
                            'default': {
                                'type': 'string',
                                'enum': [ACTION_ACCEPT, ACTION_REJECT, ACTION_SKIP],
                                'default': ACTION_REJECT,
                            },
                        },
                        'additionalProperties': {
                            'type': 'string',
                            'enum': [ACTION_ACCEPT, ACTION_REJECT, ACTION_SKIP],
                        },
                    },
                ]
            },
        },
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

        if (
            not isinstance(lang, str)
            or lang == ''
            or lang == 'und'
            or lang == UNKNOWN
            or lang == NATIVE
            or lang == DEFAULT
        ):
            return False

        try:
            mycode = Language.frommycode(lang)
            if mycode:
                lang = mycode.name
        except babelfish.LanguageReverseError:
            pass

        try:
            language = Language.fromietf(lang)
        except ValueError:
            try:
                language = Language.fromcode(lang, 'name')
            except ValueError:
                return False
            except babelfish.LanguageReverseError:
                return False

        if isinstance(language, Language):
            return True

        return False

    def _get_language(self, lang: Union[str, Language]) -> str:
        """Returns the language in text format

        Args:
            lang (Union[str, Language]): Language to return

        Returns:
            str: Language text
        """

        if isinstance(lang, Language):
            lang = lang.name

        if not isinstance(lang, str) or lang == '' or lang == 'und' or lang == UNKNOWN:
            return UNKNOWN

        if lang == NATIVE:
            return NATIVE

        if lang == DEFAULT:
            return DEFAULT

        try:
            mycode = Language.frommycode(lang)
            if mycode:
                lang = mycode.name
        except babelfish.LanguageReverseError:
            pass

        try:
            language = Language.fromietf(lang)
        except ValueError:
            try:
                language = Language.fromcode(lang, 'name')
            except ValueError:
                language = lang
            except babelfish.LanguageReverseError:
                language = lang

        if isinstance(language, Language):
            language = language.name

        return language.lower()

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

        _config['source'] = config.get('source', 'title')

        _languages_synonyms = config.get('languages_synonyms', [])
        _config['languages_synonyms'] = {}
        for lang in _languages_synonyms:
            if not self._is_language(lang):
                raise plugin.PluginError(f'`{lang}` in languages_synonyms is not a valid language')
            lang = self._get_language(lang)
            language = Language.fromcode(lang, 'name')
            _config['languages_synonyms'][language.alpha3] = _languages_synonyms[lang]
            MyCodeConverter.SYMBOLS[language.alpha3] = _languages_synonyms[lang]

        _config['languages'] = config.get('languages', [])
        if not isinstance(_config['languages'], list):
            _config['languages'] = [_config['languages']]

        _action = config.get('action', False)
        if not isinstance(_action, dict):
            _action = {
                DEFAULT: _action,
                NATIVE: ACTION_ACCEPT if _action == ACTION_REJECT else ACTION_ACCEPT,
                UNKNOWN: ACTION_REJECT,
            }

        _config['action'] = {}
        for key in _action:
            key = key.lower()
            if not key in [UNKNOWN, DEFAULT, NATIVE] and not self._is_language(key):
                raise plugin.PluginError(f'`{key}` in action is not a valid language')

            lang = self._get_language(key)
            _config['action'][lang] = _action[key]

        return _config

    def _language_to_action(self, lang: str, stream_languages: List[str], config: dict) -> str:
        """Gets the action to preform to a given language

        Args:
            lang (str): Language to process
            stream_languages (List[str]): List of the streamed languages for the media
            config (dict): Plugin config

        Returns:
            str: Action to preform
        """

        if config['action'].get(lang):
            return config['action'].get(lang), lang

        if lang in stream_languages:
            lang = NATIVE

        return config['action'].get(lang, config['action'].get(DEFAULT, ACTION_SKIP)), lang

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

            if not my_config['source'] in entry:
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

            guess['single_value'] = True
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
                file_language = NATIVE
                logger.debug('`{}` is assumed not dubbed', title)

            stream_languages = {}
            for source in my_config['languages']:
                if self._is_language(source):
                    logger.debug('Using `{}` as source language', source)
                    language = self._get_language(source)
                    stream_languages[language] = True
                    continue

                if not source in entry:
                    logger.warning('Entry does not contain a field called `{}`', source)
                    continue

                languages = entry.get(source)
                if not isinstance(languages, list):
                    languages = [languages]

                for lang in languages:
                    if not lang:
                        continue

                    language = self._get_language(lang)
                    stream_languages[language] = True

            stream_languages = list(stream_languages.keys())

            logger.debug('Processing `{}` with native language `{}`', real_title, stream_languages)

            action, f_language = self._language_to_action(
                file_language, stream_languages, my_config
            )

            if action == ACTION_SKIP:
                logger.debug('Skiping `{}` because is in language is `{}`', title, f_language)
                continue
            elif action == ACTION_REJECT:
                entry.reject(f'`{title}` is `{f_language}` language')
                continue
            elif action == ACTION_ACCEPT:
                entry.accept(f'`{title}` is `{f_language}` language')
                continue


@event('plugin.register')
def register_plugin():
    plugin.register(Dubbed, PLUGIN_NAME, api_ver=2)
