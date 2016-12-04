from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from datetime import datetime, timedelta

from flexget.config_schema import one_or_more
from past.builtins import basestring

import logging

from flexget import plugin
from flexget.event import event

__author__ = 'andy'

log = logging.getLogger('sort_by_weighted')

SUPPORTED_TYPES = (
    int,
    float,
    bool,
    datetime,
    timedelta
)

ENTRY_NAME = 'sort_by_weight_sum'
DEFAULT_SLOTS = 10


class PluginSortByWeighted(object):
    """
    Sort task entries based on a field

    Example::

      sort_by: title

    More complex::

      sort_by:
        field: imdb_score
    """

    schema = {
        'type': 'array', 'items': {
            'type': 'object',
            'properties': {
                'field': {'type': 'string'},
                'weight': {'type': 'integer', 'minimum': 5},
                'weight_default': {'type': 'integer', 'default': 0},
                'inverse': {'type': 'boolean', 'default': False},
                'delta_distance': {'type': 'integer', 'minimum': 1},
                'limits_min_max': {'type': 'array', 'items': {'type': 'integer'}, 'minItems': 2, 'maxItems': 2},
            },
            'required': ['field', 'weight'],
            'additionalProperties': False,
        },
        'minItems': 2
    }

    #    def on_task_start(self, task, config):
    def on_task_filter(self, task, config):
        # [field] = [weight, weight_default, delta, inverse, [min,max]]
        settings = {}
        for centry in config:
            if isinstance(centry, dict):
                if centry.get('field') and not centry.get('field').isspace():
                    key = centry.get('field')
                    settings[key] = [centry.get('weight', 25),
                                     centry.get('weight_default', 0),
                                     centry.get('delta_distance', -1),
                                     centry.get('inverse', False)]
                    if 'limits_min_max' in centry and isinstance(centry['limits_min_max'], list):
                        if len(centry['limits_min_max']) == 2:
                            settings[key].append(centry['limits_min_max'])

        # update delta_distance, add limits_min_max
        max_values = self.get_max_values(settings, task)
        # fix delta_distance
        for key in settings.keys():
            if settings[key][2] == -1:
                if key in max_values and max_values[key] > 0:
                    settings[key][2] == max_values[key] / DEFAULT_SLOTS
        # calcu/fill result in ENTRY_NAME
        self.calculate_weights(task, settings, max_values)
        log.debug('sorting entries by weight: %s' % config)
        task.all_entries.sort(key=lambda e: e.get(ENTRY_NAME, 0))

    @staticmethod
    def get_value(key, entry, settings):
        value = None
        if isinstance(entry[key], SUPPORTED_TYPES):
            value = entry[key]
            if isinstance(value, datetime):
                value = (datetime.now() - value).days
            elif isinstance(value, timedelta):
                value = value.days
            elif isinstance(value, bool):
                value = int(value)
            if len(settings[key]) == 5:
                value = min(value, settings[key][4][1])
                if value < settings[key][4][0]:
                    value = 0
        return value

    def calculate_weights(self, task, settings, max_values):
        # [field] = [weight, weight_default, delta, inverse, [min,max]]
        for entry in task.all_entries:
            # entry['weights'] = dict()
            weight_sum = 0
            for key in settings.keys():
                value = self.get_value(key, entry, settings)
                if value is None:
                    weight_sum += settings[key][1]  # use default weight
                    continue
                # slots = max / delta
                # step = max_weight / slots
                # weight = (entry / delta) * step
                slots = max_values[key] / settings[key][2]
                step = settings[key][0] / slots
                weight = (value / settings[key][2]) * step
                if settings[key][3] is True:
                    weight_sum += settings[key][0] - int(weight)
                else:
                    weight_sum += int(weight)
            entry[ENTRY_NAME] = weight_sum

    def get_max_values(self, settings, task):
        max_values = {}
        for entry in task.all_entries:
            for key in settings.keys():
                if key in entry:
                    if not isinstance(entry[key], SUPPORTED_TYPES):
                        log.warning('Unsupported type detected in entry: %s field: %s' % (entry, key))
                        settings[key][0] = -1  # flag invalid
                        max_values[key] = -1
                    else:
                        value = self.get_value(key, entry, settings)
                        if value is None:
                            continue
                        if key not in max_values:
                            if len(settings[key]) == 5:
                                max_value = min(value, settings[key][4][1])
                            else:
                                max_value = value
                        else:
                            if len(settings[key]) == 5:
                                max_value = max(max_values[key], min(value, settings[key][4][1]))
                            else:
                                max_value = max(max_values[key], value)
                        max_values[key] = max_value
        return max_values


@event('plugin.register')
def register_plugin():
    plugin.register(PluginSortByWeighted, 'sort_by_weighted', api_ver=2)
