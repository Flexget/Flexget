from loguru import logger

from flexget import plugin
from flexget.event import event

from . import series as plugin_series

try:
    # NOTE: Importing other plugins is discouraged!
    from flexget.components.parsing.parsers import parser_common as plugin_parser_common
except ImportError:
    raise plugin.DependencyError(issued_by=__name__, missing='parser_common')

logger = logger.bind(name='metainfo_series')


class MetainfoSeries:
    """
    Check if entry appears to be a series, and populate series info if so.
    """

    schema = {'type': 'boolean'}

    # Run after series plugin so we don't try to re-parse it's entries
    @plugin.priority(120)
    def on_task_metainfo(self, task, config):
        # Don't run if we are disabled
        if config is False:
            return
        for entry in task.entries:
            # If series plugin already parsed this, don't touch it.
            if entry.get('series_name'):
                continue
            self.guess_entry(entry)

    def guess_entry(self, entry, allow_seasonless=False, config=None):
        """
        Populates series_* fields for entries that are successfully parsed.

        :param dict config: A series config to be used. This will also cause 'path' and 'set' fields to be populated.
        """
        if entry.get('series_parser') and entry['series_parser'].valid:
            # Return true if we already parsed this, false if series plugin parsed it
            return True
        identified_by = 'auto'
        if config and 'identified_by' in config:
            identified_by = config['identified_by']
        parsed = plugin.get('parsing', self).parse_series(
            data=entry['title'], identified_by=identified_by, allow_seasonless=allow_seasonless
        )
        if parsed and parsed.valid:
            parsed.name = plugin_parser_common.normalize_name(
                plugin_parser_common.remove_dirt(parsed.name)
            )
            plugin_series.populate_entry_fields(entry, parsed, config)
            entry['series_guessed'] = True
            return True
        return False


@event('plugin.register')
def register_plugin():
    plugin.register(MetainfoSeries, 'metainfo_series', api_ver=2)
