from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.plugin import PluginInfo
from flexget.task import Task
from flexget.utils.tools import parse_timedelta

logger = logger.bind(name='est_released')
ESTIMATOR_INTERFACE = "estimate_release"

# Mapping of available estimate providers to plugin instance
estimators = {}
# Task specific estimate configuration
task_estimate_config: Dict[str, Any] = {}

# We need to wait until manager startup to access other plugin instances, to make sure they have all been loaded
@event('manager.startup')
def init_estimators(manager) -> None:
    """Prepare the list of available estimator plugins."""

    estimators = {
        p.name.replace('est_', ''): p for p in plugin.get_plugins(interface=ESTIMATOR_INTERFACE)
    }

    logger.debug('setting default estimators to {}', list(estimators.keys()))


class EstimateRelease:
    """
    Front-end for estimator plugins that estimate release times
    for various things (series, movies).
    """

    @property
    def schema(self) -> Dict[str, Any]:
        """Create schema for that allows configuring estimator providers and
        related settings.
        """

        schema = {
            'type': 'object',
            'properties': {
                'providers': {
                    'type': 'array',
                    'items': {
                        'type': 'string',
                        'enum': [
                            p.name.replace('est_', '')
                            for p in plugin.get_plugins(interface=ESTIMATOR_INTERFACE)
                        ],
                    },
                },
                'offset': {'type': 'string', 'format': 'interval', 'default': '0 days'},
            },
            'additionalProperties': False,
        }

        return schema

    def on_task_start(self, task: Task, config) -> None:
        # Load task specific estimator configuration
        if config:
            self.task_estimate_config = config

    def on_task_exit(self, task: Task, config) -> None:
        # Restore default estimator configuration for next task run
        self.task_estimate_config = {}

    on_task_abort = on_task_exit

    def get_estimators(self) -> List[PluginInfo]:
        """
        Returns the list of configured estimator providers for the task.  If no
        providers are configured, all available providers are returned.

        Providers are sorted by the plugin priority.

        :return: Sorted list of estimator plugin instances.
        """
        if "providers" in self.task_estimate_config:
            # Map task configured providers to plugin instance map
            task_estimators = [
                estimators[p].instance.estimate for p in self.task_estimate_config['providers']
            ]
        else:
            # Use all loaded estimator plugins
            task_estimators = [e.instance.estimate for e in estimators]

        return sorted(
            task_estimators,
            key=lambda e: getattr(e, 'priority', plugin.PRIORITY_DEFAULT),
            reverse=True,
        )

    @property
    def offset(self) -> str:
        """
        Return the configured offset for the task.
        """
        return self.task_estimate_config.get('offset', '0 days')

    def estimate(self, entry) -> Dict[str, Union[bool, Optional[datetime]]]:
        """
        Estimate release schedule for entry

        :param entry:
        :return: estimated date of released for the entry, None if it can't figure it out
        """

        logger.debug(f"estimating release date for {entry['title']}")
        for estimator in self.get_estimators():
            estimate = estimator(entry)
            # Return first successful estimation
            if estimate is not None:
                estimation = estimate
                break
        else:
            estimation = {'data_exists': False, 'entity_date': None}

        if estimation['entity_date']:
            estimation['entity_date'] = estimation['entity_date'] + parse_timedelta(self.offset)

        return estimation


@event('plugin.register')
def register_plugin():
    plugin.register(EstimateRelease, 'estimate_release', api_ver=2)
