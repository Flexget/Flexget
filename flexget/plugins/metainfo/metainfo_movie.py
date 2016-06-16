from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget.plugins.parsers.parser_common import normalize_name, remove_dirt
from flexget import plugin
from flexget.event import event
from flexget.plugin import get_plugin_by_name

log = logging.getLogger('metainfo_movie')


class MetainfoMovie(object):
    """
    Check if entry appears to be a movie, and populate movie info if so.
    """

    schema = {'type': 'boolean'}

    def on_task_metainfo(self, task, config):
        # Don't run if we are disabled
        if config is False:
            return
        for entry in task.entries:
            # If movie parser already parsed this, don't touch it.
            if entry.get('movie_name'):
                continue
            self.guess_entry(entry)

    @staticmethod
    def guess_entry(entry):
        """
        Populates movie_* fields for entries that are successfully parsed.
        :param entry: Entry that's being processed
        :return: True for successful parse
        """
        if entry.get('movie_guessed'):
            # Return true if we already parsed this
            return True
        parser = get_plugin_by_name('parsing').instance.parse_movie(data=entry['title'])
        if parser and parser.valid:
            parser.name = normalize_name(remove_dirt(parser.name))
            entry.update(parser.fields)
            return True
        return False


@event('plugin.register')
def register_plugin():
    plugin.register(MetainfoMovie, 'metainfo_movie', api_ver=2)
