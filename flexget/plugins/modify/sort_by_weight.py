from datetime import datetime, timedelta

from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.utils.qualities import Quality
from flexget.utils.tools import parse_timedelta

__author__ = 'andy'

logger = logger.bind(name='sort_by_weight')

ENTRY_WEIGHT_FIELD_NAME = 'sort_by_weight_sum'
DEFAULT_STRIDE = (
    10  # its a design choice to allow 'similar' values to-be grouped under the same slot/weight
)


class PluginSortByWeight:
    """
    Sort task entries based on multiple fields using a sort weight per field.
    Result per entry is stored in 'sort_by_weight_sum'.

    Basic Concept:
    For each field we calculate a weight based on given parameters and than sum the weights up and do a sort based on it.

    field:          Name of the sort field
    weight:         The sort weight used, values between 10-200 are good starts
    inverse: yes    Use inverse weighting for the field, example: date, age fields that range in the past
                    This means the lowest entry/value will get the highest weight
    upper_limit:    The upper value limit or upper cutoff value, that will be used for weighting.
                    This will change the slot distribution, which helps narrow down to more meaningfully weighting results.

                    Example: Entry1 is 100 days old, Entry2 is 7 days old, Entry3 is 1000 days old
                    Without a upper_limit the weights will be distributed between 0-1000 days, with a upper_limit: 100 days
                    weights will be distributed between 0-100 days and any value larger than upper_limit, gets the highest score.
                    So we can smoothly distribute the rest between 0-100 days.

    delta_distance: The distance, step until a new slot is used for weighting.
                    Think of this like: Any value that is within this distance will get the same weight for the step.
                    NOTE: If not given the delta_distance will be distributed over 10 distinct steps

                    Example: Size1 = 4000 MB, Size2 = 3000 MB, Size3 = 700 MB
                             With a weight: 50 and delta_distance: 1200
                             Size1 and Size2 both get the maximum weight of 50, while Size3 gets the weight for the 0-1200 MB step.

    Example::
        simple:
        sort_by_weight:
            - field: quality
                weight: 100         # quality is most important, use highest weight
            - field: content_size
                weight: 70          # size is still a good quality estimate so use a high weight
            - field: newznab_pubdate
                weight: 30          # age is somewhat important so use low weight
                inverse: yes

        advanced:
        sort_by_weight:
          - field: content_size
            weight: 80              # we want large files mainly = good quality
            delta_distance: 500     # anything within 500 MB gets the same weight
            upper_limit: 8000       # anything over 8000 MB is fine and will get the max weight (80)
          - field: newznab_pubdate
            weight: 30              # we still like new releases
            upper_limit: 60 days    # anything older 60 days gets the lowest weight (because of inverse: yes)
            inverse: yes            # reverse weight order for date/age fields
          - field: newznab_grabs
            weight: 20              # we like releases that others already downloaded
            upper_limit: 100        # anything over 100 grabs is fine and gets maximum weight

            In this example the best result can have a 'sort_by_weight_sum' of sum = 80 + 30 + 20
    """

    schema = {
        'type': 'array',
        'items': {
            'type': 'object',
            'properties': {
                'field': {'type': 'string'},
                'weight': {'type': 'integer', 'minimum': 5},
                'inverse': {'type': 'boolean', 'default': False},
                'upper_limit': {
                    'oneOf': [
                        {'type': 'integer', 'minimum': 1},
                        {'type': 'string', 'format': 'interval'},
                    ]
                },
                'delta_distance': {
                    'oneOf': [
                        {'type': 'integer', 'minimum': 1},
                        {'type': 'string', 'format': 'interval'},
                    ]
                },
            },
            'required': ['field', 'weight'],
            'additionalProperties': False,
        },
        'minItems': 2,
    }

    def prepare_config(self, config):
        settings = {}
        for entry in config:
            if isinstance(entry, dict):
                if entry.get('field') and not entry.get('field').isspace():
                    key = entry.get('field')
                    settings[key] = entry
                    delta = settings[key].get('delta_distance')
                    if delta and isinstance(delta, str):
                        settings[key]['delta_distance'] = parse_timedelta(delta)
                    limit = settings[key].get('upper_limit')
                    if limit and isinstance(limit, str):
                        settings[key]['upper_limit'] = parse_timedelta(limit)
        return settings

    @plugin.priority(127)  # run after default filters
    def on_task_filter(self, task, config):
        entries = list(task.accepted) + list(task.undecided)  # ['undecided', 'accepted']
        if len(entries) < 2:
            return
        config = self.prepare_config(config)
        logger.verbose(
            'Calculating weights for undecided, accepted entries and sorting by result field: {}',
            ENTRY_WEIGHT_FIELD_NAME,
        )
        self.calc_weights(entries, config)
        task.all_entries.sort(key=lambda e: e.get(ENTRY_WEIGHT_FIELD_NAME, 0), reverse=True)
        # debug
        # for entry in task.all_entries:
        #    log.verbose('sum[ %s ] weights: %s, title: %s', entry.get(ENTRY_WEIGHT_FIELD_NAME, -1), entry.get('weights', -1), entry['title'])

    @staticmethod
    def _get_lower_limit(value):
        min_value = 0
        if isinstance(value, Quality):
            min_value = Quality()
        elif isinstance(value, bool):
            min_value = False
        elif isinstance(value, datetime):
            min_value = datetime.now()  # assume date comparision vs now()
        elif isinstance(value, timedelta):
            min_value = timedelta(0)
        return min_value

    @staticmethod
    def _limit_value(key, value, config):
        if config[key].get('upper_limit'):
            limit = config[key]['upper_limit']
            # auto handle datetime
            if isinstance(value, datetime) and isinstance(limit, timedelta):
                if config[key]['inverse'] is True:
                    if (datetime.now() - limit) > value:
                        value = datetime.now() - limit
                else:
                    if (datetime.now() + limit) < value:
                        value = datetime.now() + limit
            elif value > limit:
                value = limit
        return value

    def _calc_stride_delta(self, key, entries, config):
        delta = None
        stride = None

        lower_default = self._get_lower_limit(entries[0][key])
        max_entry = max(entries, key=lambda e, k=key, d=lower_default: e.get(k, d))
        min_entry = min(entries, key=lambda e, k=key, d=lower_default: e.get(k, d))
        max_value = max_entry[key]
        max_value = self._limit_value(key, max_value, config)
        min_value = min_entry[key]
        try:
            min_value = min(min_value, lower_default)  # try normalize to natural lower bound
        except Exception as ex:
            logger.debug('Incompatible min_value op: {}', ex)

        value_range = max_value - min_value
        if value_range:
            if 'delta_distance' in config[key]:
                delta = config[key]['delta_distance']
                stride = value_range / delta
                if isinstance(stride, timedelta):
                    stride = stride.days
            else:
                delta = value_range / DEFAULT_STRIDE
        return stride, delta

    def calc_weights(self, entries, config):
        for key in config:
            if key not in entries[0]:
                continue
            # stride = max / delta
            # step = max_weight / stride
            # weight = (entry / delta) * step
            stride = None
            delta = None
            try:
                stride, delta = self._calc_stride_delta(key, entries, config)
            except Exception as ex:
                delta = None
                logger.warning(
                    'Could not calculate stride for key: {}, type: {}, using fallback sort. Error: {}',
                    key,
                    type(entries[0][key]),
                    ex,
                )
                lower_default = self._get_lower_limit(entries[0][key])
                entries.sort(key=lambda e, k=key, d=lower_default: e.get(k, d), reverse=True)
            if not stride:
                stride = DEFAULT_STRIDE
            max_weight = config[key]['weight']
            weight_step = max_weight / max(int(stride), 1)
            current_value = None
            weight = None
            # log.verbose('*** key: `%s`, delta: %s, weight_step: %s', key, delta, weight_step)
            for entry in entries:
                if ENTRY_WEIGHT_FIELD_NAME not in entry:
                    entry[ENTRY_WEIGHT_FIELD_NAME] = 0

                value = entry[key]
                value = self._limit_value(key, value, config)
                if value is None:
                    continue
                if current_value is None:
                    current_value = value
                if weight is None:
                    weight = max_weight

                if delta:
                    try:
                        weight = (value / delta) * weight_step
                    except Exception:
                        try:
                            # convert value to distance from minimum
                            value_normalized = abs(value - self._get_lower_limit(value))
                            weight = (value_normalized / delta) * weight_step
                        except Exception as ex:
                            logger.warning(
                                'Skipping entry: {}, could not calc weight for key: {}, error: {}',
                                entry,
                                key,
                                ex,
                            )
                            continue
                    current_value = value
                elif value < current_value:
                    weight = weight - weight_step
                    current_value = value
                if config[key]['inverse'] is True:
                    weight = max_weight - weight

                weight = int(max(weight, 0))
                entry[ENTRY_WEIGHT_FIELD_NAME] += weight
                # self._add_debug_info(key, entry, weight, entry[key], value)  # debug only

    def _add_debug_info(self, key, entry, weight, *args):
        if 'weights' not in entry:
            entry['weights'] = {}
        short_args = []
        for arg in args:
            if isinstance(arg, timedelta):
                short_args.append(arg.days)
            elif isinstance(arg, datetime):
                date = arg.date()
                short_args.append(f'{date.year}-{date.month}-{date.day}')
            elif isinstance(arg, Quality):
                quality_string = '[ {} ]-{}-{}, [ {} ]'.format(
                    arg.resolution,
                    arg.source,
                    arg.codec,
                    arg.audio,
                )
                if quality_string not in short_args:
                    short_args.append(quality_string)
            else:
                short_args.append(arg)
        entry['weights'][key] = f'{weight} = {short_args}'


@event('plugin.register')
def register_plugin():
    plugin.register(PluginSortByWeight, 'sort_by_weight', api_ver=2)
