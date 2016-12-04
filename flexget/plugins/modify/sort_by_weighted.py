from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from datetime import datetime, timedelta

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
    Sort task entries based on multiple fields using a sort weight per field.
    Result per entry is stored in 'sort_by_weight_sum'.

    Basic Concept:
    For each field we calculate a weight based on given parameters and than sum the weights up and do a sort based on it.

    field:          Name of the sort field
    weight:         The sort weight used, values between 10-200 are good starts
    weight_default: The default weight used if a sort 'field' could not be found or had a invalid entry (default is: 0)
    inverse:        Use inverse weighting for the field, example: Date/Age fields
    limits_min_max: The minimum cutoff and maximum cutoff value, that will be used for weighting.
                    This will change the slot distribution, which helps narrow down to more meaningfully weighting results.

                    Example: Entry1 is 100 days old, Entry2 is 7 days old, Entry3 is 1000 days old
                    Without a max cutoff the weights will be distributed between 0-1000 days, with a limits_min_max: [0, 100]
                    Weights will be distributed between 0-100 and any value larger than max, gets the lowest weight,
                    while we can smoothly distribute the rest between 0-100 days.

    delta_distance: The distance, step until a new slot is used for weighting.
                    Think of this like: Any value that is within this distance will get the same weight for the slot.
                    NOTE: If not given the delta_distance will be distributed over 10 slots/steps

                    Example: Size1 = 4000 MB, Size2 = 3000 MB, Size3 = 700 MB
                             With a weight: 50 and delta_distance: 1000
                             Size1 and Size2 both get the maximum weight of 50, while Size3 gets the weight for the 0-1000 MB slot.

    Example::
        sort_by_weighted:
          - field: content_size
            weight: 80              # we want large files mainly = good quality
            delta_distance: 500     # anything within 500 MB gets the same weight
          - field: newznab_pubdate
            weight: 25              # we still like new releases
            delta_distance: 7       # anything within 7 days is similar
            limits_min_max: [0,60]  # confine results to 0-60 days
            inverse: yes            # reverse weight order for date/age fields
          - field: newznab_grabs
            weight: 25              # we like releases that others already downloaded aka safeguard against crap
            limits_min_max: [0,100] # anything over 100 grabs is fine and gets maximum weight
            weight_default: 5       # if entry has no 'newznab_grabs' field, still use 5 as weight so they don't sink to the bottom to quickly.

            In this example the best result can have a 'sort_by_weight_sum' of sum = 80 + 25 + 25
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
                    settings[key][2] = max_values[key] / DEFAULT_SLOTS
        # calcu/fill result in ENTRY_NAME
        self.calculate_weights(task, settings, max_values)
        log.debug('sorting entries by weight: %s' % config)
        task.all_entries.sort(key=lambda e: e.get(ENTRY_NAME, 0), reverse=True)

    @staticmethod
    def get_value(key, entry, settings):
        value = None
        if key in entry and isinstance(entry[key], SUPPORTED_TYPES):
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
