from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget.plugins.parsers.parser_common import normalize_name, remove_dirt
from flexget import plugin
from flexget.event import event
from flexget.plugin import get_plugin_by_name
from flexget.plugins.parsers.parser_guessit import GuessitParsedEntry

log = logging.getLogger('metainfo_movie')


class MetainfoMovie(object):
    """
    Check if entry appears to be a movie, and populate movie info if so.
    """

    schema = {'type': 'boolean'}

    @staticmethod
    def populate_entry_fields(entry, parsed):
        entry['movie_parser'] = parsed
        entry['movie_name'] = parsed.name
        entry['movie_year'] = parsed.year
        entry['proper'] = parsed.proper
        entry['proper_count'] = parsed.proper_count

        if isinstance(parsed, GuessitParsedEntry):
            entry['release_group'] = parsed.parsed_group
            entry['is_3d'] = parsed.is_3d
            entry['subtitle_languages'] = parsed.subtitle_languages
            entry['languages'] = parsed.languages
            entry['video_codec'] = parsed.quality2.video_codec
            entry['format'] = parsed.quality2.format
            entry['audio_codec'] = parsed.quality2.audio_codec
            entry['video_profile'] = parsed.quality2.video_profile
            entry['screen_size'] = parsed.quality2.screen_size
            entry['audio_channels'] = parsed.quality2.audio_channels
            entry['audio_profile'] = parsed.quality2.audio_profile

        entry['movie_guessed'] = True

    def on_task_metainfo(self, task, config):
        # Don't run if we are disabled
        if config is False:
            return
        for entry in task.entries:
            # If movie parser already parsed this, don't touch it.
            if entry.get('movie_name'):
                continue
            self.guess_entry(entry)

    def guess_entry(self, entry):
        """
        Populates movie_* fields for entries that are successfully parsed.
        :param entry: Entry that's being processed
        :return: True for successful parse
        """
        if entry.get('movie_parser') and entry['movie_parser'].valid:
            # Return true if we already parsed this
            return True
        parsed = get_plugin_by_name('parsing').instance.parse_movie(data=entry['title'])
        if parsed and parsed.valid:
            parsed.name = normalize_name(remove_dirt(parsed.name))
            self.populate_entry_fields(entry, parsed)
            return True
        return False


@event('plugin.register')
def register_plugin():
    plugin.register(MetainfoMovie, 'metainfo_movie', api_ver=2)
