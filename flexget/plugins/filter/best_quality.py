from loguru import logger

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.tools import group_entries

logger = logger.bind(name='best_quality')

entry_actions = {'accept': Entry.accept, 'reject': Entry.reject}


class FilterBestQuality:
    schema = {
        'type': 'object',
        'properties': {
            'identified_by': {'type': 'string', 'default': 'auto'},
            'on_best': {
                'type': 'string',
                'enum': ['accept', 'reject', 'do_nothing'],
                'default': 'do_nothing',
            },
            'on_lower': {
                'type': 'string',
                'enum': ['accept', 'reject', 'do_nothing'],
                'default': 'reject',
            },
            'single_best': {
                'type': 'boolean',
                'default': True,
            },
        },
        'additionalProperties': False,
    }

    def on_task_filter(self, task, config):
        if not config:
            return

        identified_by = (
            '{{ media_id }}' if config['identified_by'] == 'auto' else config['identified_by']
        )

        action_on_best = (
            entry_actions[config['on_best']] if config['on_best'] != 'do_nothing' else None
        )
        action_on_lower = (
            entry_actions[config['on_lower']] if config['on_lower'] != 'do_nothing' else None
        )

        grouped_entries = group_entries(task.accepted + task.undecided, identified_by)

        for identifier, entries in grouped_entries.items():
            if not entries:
                continue

            # Sort entities in order of quality and best proper
            entries.sort(key=lambda e: (e['quality'], e.get('proper_count', 0)), reverse=True)

            if config['single_best']:
                # First entry will be the best quality
                best = entries.pop(0)

                if action_on_best:
                    action_on_best(best, 'has the best quality for identifier %s' % identifier)

                if action_on_lower:
                    for entry in entries:
                        action_on_lower(entry, 'lower quality for identifier %s' % identifier)
            else:
                # Store the best quality for comparison
                best_quality = entries[0]['quality']
                for entry in entries:
                    if action_on_best and entry['quality'] == best_quality:
                        action_on_best(
                            entry, 'has the best quality for identifier %s' % identifier
                        )
                    if action_on_lower and entry['quality'] < best_quality:
                        action_on_lower(entry, 'lower quality for identifier %s' % identifier)


@event('plugin.register')
def register_plugin():
    plugin.register(FilterBestQuality, 'best_quality', api_ver=2)
