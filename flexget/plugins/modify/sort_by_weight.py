from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from datetime import datetime, timedelta

import logging

from flexget.utils.tools import parse_timedelta
from past.types import basestring

from flexget.utils.qualities import Quality

from flexget import plugin
from flexget.event import event

__author__ = 'andy'

log = logging.getLogger('sort_by_weight')

ENTRY_WEIGHT_FIELD_NAME = 'sort_by_weight_sum'
DEFAULT_STRIDE = 20  # its a design choice to allow 'similar' values to-be grouped under the same slot/weight

class PluginSortByWeight(object):
    """
    Sort task entries based on multiple fields using a sort weight per field.
    Result per entry is stored in 'sort_by_weight_sum'.

    Basic Concept:
    For each field we calculate a weight based on given parameters and than sum the weights up and do a sort based on it.

    field:          Name of the sort field
    weight:         The sort weight used, values between 10-200 are good starts
    weight_default: The default weight used if a sort 'field' could not be found or had a invalid entry (default is: 0)
    inverse:        Use inverse weighting for the field, example: Date/Age fields
    upper_limit:    The upper value limit or upper cutoff value, that will be used for weighting.
                    This will change the slot distribution, which helps narrow down to more meaningfully weighting results.

                    Example: Entry1 is 100 days old, Entry2 is 7 days old, Entry3 is 1000 days old
                    Without a upper_limit the weights will be distributed between 0-1000 days, with a upper_limit: 100
                    weights will be distributed between 0-100 and any value larger than upper_limit, gets the highest score.
                    So we can smoothly distribute the rest between 0-100 days.
    lower_limit:    Similar to upper_limit, so each field value under this limit gets the lowest weight score.

    delta_distance: The distance, step until a new slot is used for weighting.
                    Think of this like: Any value that is within this distance will get the same weight for the slot.
                    NOTE: If not given the delta_distance will be distributed over 10 slots/steps

                    Example: Size1 = 4000 MB, Size2 = 3000 MB, Size3 = 700 MB
                             With a weight: 50 and delta_distance: 1000
                             Size1 and Size2 both get the maximum weight of 50, while Size3 gets the weight for the 0-1000 MB slot.

    Example::
        sort_by_weight:
          - field: content_size
            weight: 80              # we want large files mainly = good quality
            delta_distance: 500     # anything within 500 MB gets the same weight
          - field: newznab_pubdate
            weight: 25              # we still like new releases
            delta_distance: 7       # anything within 7 days is similar
            upper_limit: 60         # confine results to 0-60 days
            inverse: yes            # reverse weight order for date/age fields
          - field: newznab_grabs
            weight: 25              # we like releases that others already downloaded aka safeguard against crap
            upper_limit: 100        # anything over 100 grabs is fine and gets maximum weight
            weight_default: 5       # if entry has no 'newznab_grabs' field, still use 5 as weight so they don't sink to the bottom to quickly.

            In this example the best result can have a 'sort_by_weight_sum' of sum = 80 + 25 + 25
    """

    schema = {
        'type': 'array', 'items': {
            'type': 'object',
            'properties': {
                'field': {'type': 'string'},
                'weight': {'type': 'integer', 'minimum': 5},
                'inverse': {'type': 'boolean', 'default': False},
                'upper_limit': {
                    'oneOf': [
                        {'type': 'integer', 'minimum': 1},
                        {'type': 'string', 'format': 'interval'}
                    ]
                },
                'delta_distance': {
                    'oneOf': [
                        {'type': 'integer', 'minimum': 1},
                        {'type': 'string', 'format': 'interval'}
                    ]
                },
            },
            'required': ['field', 'weight'],
            'additionalProperties': False,
        },
        'minItems': 2
    }

    def prepare_config(self, config):
        settings = {}
        for entry in config:
            if isinstance(entry, dict):
                if entry.get('field') and not entry.get('field').isspace():
                    key = entry.get('field')
                    settings[key] = entry
                    delta = settings[key].get('delta_distance')
                    if delta and isinstance(delta, basestring):
                        settings[key]['delta_distance'] = parse_timedelta(delta)
                    limit = settings[key].get('upper_limit')
                    if limit and isinstance(limit, basestring):
                        settings[key]['upper_limit'] = parse_timedelta(limit)
        return settings

    @plugin.priority(127)  # run after default filters
    def on_task_filter(self, task, config):
        entries = list(task.accepted) + list(task.undecided)  # ['undecided', 'accepted']
        if len(entries) < 2:
            return
        config = self.prepare_config(config)
        log.info('sorting ´undecided´,´accepted´ entries by weight!')
        # update delta_distance, calc 'max_value'
        #self.calc_prepare_values(entries, config)
        # calc/fill result in 'sort_by_weight_sum'
        #self.calculate_weights(entries, config)
        self.calc_weights_new(entries, config)

        task.all_entries.sort(key=lambda e: e.get(ENTRY_WEIGHT_FIELD_NAME, 0), reverse=True)

        for e in entries:
            log.verbose(e['weights'])
        # log.verbose('size: %s' % len(entries))
        # for e in task.entries:
        #     log.verbose('[%s] idx[%s] size[%s] age[%s] grabs[%s] title[%s]' % (e.get('sort_by_weight_sum', -1),
        #                                                                        e['newznab_hydraindexerscore'],
        #                                                                        e['content_size'],
        #                                                                        e['newznab_age'],
        #                                                                        e['newznab_grabs'],
        #                                                                        e['title']))

    @staticmethod
    def get_lower_limit(value):
        min_value = 0
        if isinstance(value, Quality):
            min_value = Quality()
        elif isinstance(value, bool):
            min_value = False
        elif isinstance(value, datetime):
            min_value = datetime.min
        elif isinstance(value, timedelta):
            min_value = timedelta(0)
        return min_value

    def limit_value(self, key, value, config):
        if config[key].get('upper_limit'):
            limit = config[key]['upper_limit']
            try:
                # auto handle datetime
                if isinstance(value, datetime) and isinstance(limit, timedelta):
                    if config[key]['inverse'] is True:
                        limit = datetime.now() - limit
                    else:
                        limit = datetime.now() + limit

                if value > limit:
                    value = limit
            except Exception as ex:
                raise plugin.PluginError('Limit failed, key: %s, value: %s, error: %s' % (key, value, ex))
        return value

    def calc_stride_delta(self, key, entries, config):
        value_range = None
        delta = None
        stride = DEFAULT_STRIDE
        try:
            max_value = max(entries, key=lambda e: e.get(key, 0))
            min_value = min(entries, key=lambda e: e.get(key, 0))
            try:
                min_value = min(min_value, 0)  # try normalize to natural lower bound
            except Exception:
                pass


            try:
                value_range = max_value - min_value
            except Exception:
                pass
        except Exception:
            pass

        if value_range:
            try:
                if 'delta_distance' in config[key]:
                    delta = config[key]['delta_distance']
                    stride = value_range / delta
            except Exception:
                delta = value_range / DEFAULT_STRIDE
                stride = DEFAULT_STRIDE

        return stride, delta

    def calc_weights_new(self, entries, config):
        for key in config:
            if key not in entries[0]:
                continue
            entries.sort(key=lambda e: e.get(key, self.get_lower_limit(e[key])), reverse=True)  # largest-> smallest by default
            # stride = max / delta
            # step = max_weight / stride
            # weight = (entry / delta) * step
            stride, delta = self.calc_stride_delta(key, entries, config)
            if not stride:
                continue
            max_weight = config[key]['weight']
            weight_step = max_weight / int(stride)
            current_value = None
            weight = None
            for entry in entries:
                if 'weights' not in entry:
                    entry['weights'] = dict()
                if ENTRY_WEIGHT_FIELD_NAME not in entry:
                    entry[ENTRY_WEIGHT_FIELD_NAME] = 0

                value = entry[key]
                value = self.limit_value(key, value, config)
                if value is None:
                    continue
                if current_value is None:
                    current_value = value
                if weight is None:
                    weight = max_weight

                if delta: # is not None and (value + delta) < current_value:
                    weight = (value / delta) * weight_step
                    weight = max(weight, 0)
                    current_value = value
                elif value < current_value:
                    weight = max(weight - weight_step, 0)
                    current_value = value

                if config[key]['inverse'] is True:
                    weight = max_weight - weight
                entry['weights'][key] = [entry[key], int(weight)]
                entry[ENTRY_WEIGHT_FIELD_NAME] += int(weight)

    def calculate_weights(self, entries, config):
        # [field] = [weight, weight_default, delta, inverse, lower_limit, upper_limit]
        for entry in entries:
            entry['weights'] = dict()
            weight_sum = 0
            for key in config.keys():
                if 'delta_distance' not in config[key] or 'max_value' not in config[key]:
                    continue
                value = self.get_value(key, entry, config)
                if value is None:
                    weight_sum += config[key]['weight_default']  # use default weight
                    continue
                # slots = max / delta
                # step = max_weight / slots
                # weight = (entry / delta) * step
                slots = config[key]['max_value'] / config[key]['delta_distance']
                step = config[key]['weight'] / slots
                weight = int(int(value / config[key]['delta_distance']) * step)
                if config[key]['inverse'] is True:
                    weight = config[key]['weight'] - weight
                weight_sum += weight
                entry['weights'][key] = [value, weight]
            entry[ENTRY_WEIGHT_FIELD_NAME] = weight_sum

    def calc_prepare_values(self, entries, config):
        # calc max values
        for entry in entries:
            for key in config:
                if key in entry:
                    if not isinstance(entry[key], SUPPORTED_TYPES):
                        log.warning('Unsupported type detected in entry: %s field: %s' % (entry, key))
                    else:
                        value = self.get_value(key, entry, config)
                        if value is None:
                            continue
                        if 'max_value' in config[key]:
                            value = max(config[key]['max_value'], value)
                        config[key]['max_value'] = value
        # fix delta_distance
        for key in config:
            if 'delta_distance' not in config[key]:
                if 'max_value' in config[key] and config[key]['max_value'] > 0:
                    config[key]['delta_distance'] = config[key]['max_value'] / DEFAULT_STRIDE


@event('plugin.register')
def register_plugin():
    plugin.register(PluginSortByWeight, 'sort_by_weight', api_ver=2)
