import re

from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.event import event
from flexget.utils.template import evaluate_expression

logger = logger.bind(name='sort_by')

RE_ARTICLES = r'^(the|a|an)\s'


class PluginSortBy:
    """
    Sort task entries based on a field

    Example::

      sort_by: title

    More complex::

      sort_by:
        field: imdb_score
        reverse: yes

    Reverse the order of the entries, without sorting on a field::

      sort_by:
        reverse: yes
    """

    schema = one_or_more(
        {
            'oneOf': [
                {'type': 'string'},
                {
                    'type': 'object',
                    'properties': {
                        'field': {'type': 'string'},
                        'reverse': {'type': 'boolean'},
                        'ignore_articles': {
                            'oneOf': [{'type': 'boolean'}, {'type': 'string', 'format': 'regex'}]
                        },
                    },
                    'additionalProperties': False,
                },
            ]
        }
    )

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_filter(self, task, config):
        if not isinstance(config, list):
            config = [config]
        # First item in the config list should be primary sort key, so iterate in reverse
        for item in reversed(config):
            if isinstance(item, str):
                field = item
                reverse = False
                ignore_articles = False
            else:
                field = item.get('field', None)
                reverse = item.get('reverse', False)
                ignore_articles = item.get('ignore_articles', False)

            logger.debug('sorting entries by: {}', item)

            if not field:
                if reverse:
                    task.all_entries.reverse()
                continue

            re_articles = RE_ARTICLES if ignore_articles is True else ignore_articles

            def sort_key(entry):
                val = evaluate_expression(field, entry)
                if isinstance(val, str) and re_articles:
                    val = re.sub(re_articles, '', val, flags=re.IGNORECASE)
                # Sort None values last no matter whether reversed or not
                return (val is not None) == reverse, val

            task.all_entries.sort(key=sort_key, reverse=reverse)


@event('plugin.register')
def register_plugin():
    plugin.register(PluginSortBy, 'sort_by', api_ver=2)
