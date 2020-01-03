from loguru import logger

from flexget import plugin
from flexget.event import event

try:
    # NOTE: Importing other plugins is discouraged!
    from flexget.components.parsing.parsers import parser_common as plugin_parser_common
except ImportError:
    raise plugin.DependencyError(issued_by=__name__, missing='parser_common')

logger = logger.bind(name='metainfo_movie')


class MetainfoMovie:
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
        parser = plugin.get('parsing', 'metainfo_movie').parse_movie(data=entry['title'])
        if parser and parser.valid:
            parser.name = plugin_parser_common.normalize_name(
                plugin_parser_common.remove_dirt(parser.name)
            )
            for field, value in parser.fields.items():
                if not entry.is_lazy(field) and not entry.get(field):
                    entry[field] = value
            return True
        return False


@event('plugin.register')
def register_plugin():
    plugin.register(MetainfoMovie, 'metainfo_movie', api_ver=2)
