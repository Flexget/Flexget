from __future__ import unicode_literals, division, absolute_import
from datetime import datetime, timedelta
import functools

UNITS = ['seconds', 'minutes', 'hours', 'days', 'weeks']
WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']


# TODO: make tests for this, the defaults probably don't work quite right at the moment
schedule_schema = {
    'type': 'object',
    'properties': {
        'every': {'type': 'number', 'default': 1},
        'unit': {'type': 'string', 'enum': UNITS + [u.rstrip('s') for u in UNITS], 'default': 'hours'},
        'on': {'type': 'string', 'enum': WEEKDAYS},
        'at': {'type': 'string'}},
    'additionalProperties': False,
    'dependencies': {
        'on': {
            'properties': {
                'amount': {'type': 'integer'},
                'unit': {
                    'enum': ['week', 'weeks'],
                    'default': 'weeks'}}},
        'at': {
            'properties': {
                'amount': {'type': 'integer'},
                'unit': {
                    'enum': ['day', 'days', 'week', 'weeks'],
                    'default': 'days'}}}}}


main_schema = {
    'properties': {
        'tasks': {'type': 'object', 'additionalProperties': schedule_schema},
        'default': schedule_schema
    }
}


class Job(object):
    def __init__(self, config=None):
        self.job_func = None
        self.unit = None
        self.amount = None
        self.on_day = None
        self._at_time = None
        self.last_run = None
        self.next_run = None

    def _validate(self):
        """Makes sure schedule is valid."""
        if not self.unit or not self.amount:
            raise ValueError('unit and amount must be specified')
        if self.unit not in UNITS:
            raise ValueError('`%s` is not a valid unit' % self.unit)
        if self.on_day and self.on_day not in WEEKDAYS:
            raise ValueError('`%s` is not a valid day of week' % self.on_day)
        if self.on_day and self.unit != 'weeks':
            raise ValueError('unit must be weeks when on_day is used')
        if self.at_time and self.unit not in ['days', 'weeks']:
            raise ValueError('unit must be days or weeks when at_time is used')
        if self.on_day or self.at_time and int(self.amount) != self.amount:
            raise ValueError('amount must be an integer when on_day or at_time are used')

    @property
    def at_time(self):
        return self._at_time

    @at_time.setter
    def at_time(self, value):
        """Allow setting the time with a 12 or 24 hour formatted time string."""
        if isinstance(value, basestring):
            # Try parsing with AM/PM first, then 24 hour time
            try:
                self._at_time = datetime.strptime(value, '%I:%M %p')
            except ValueError:
                try:
                    self._at_time = datetime.strptime(value, '%H:%M')
                except ValueError:
                    raise ValueError('invalid time `%s`' % value)
        else:
            self._at_time = value

    def set_func(self, func, *args, **kwargs):
        self.job_func = functools.partial(func, *args, **kwargs)

    @property
    def should_run(self):
        return datetime.datetime.now() >= self.next_run

    @property
    def period(self):
        return datetime.timedelta(**{self.unit: self.amount})

    def schedule_next_run(self):
        last_run = self.last_run
        if not last_run:
            # Pretend we ran one period ago
            last_run = datetime.now() - self.period
        if self.on_day:
            days_ahead = self.on_day - last_run.weekday()
            if days_ahead <= 0:  # Target day already happened this week
                days_ahead += 7
            self.next_run = last_run + datetime.timedelta(days=days_ahead, weeks=self.amount-1)
        else:
            self.next_run = last_run + self.period
        if self.at_time:
            self.next_run = self.next_run.replace(hour=self.at_time.hour, minute=self.at_time.minute,
                                                  second=self.at_time.second)

    # TODO: Probably remove this, and go with the yaml form defined by above schema
    # format: every NUM UNIT [on WEEKDAY] [at TIME]
    def parse_schedule_text(self, text):
        result = {}
        word_iter = iter(text.lower().split(' '))
        try:
            if next(word_iter, '') != 'every':
                raise ValueError('schedule string must start with `every`')
            word = next(word_iter, '')
            try:
                self.amount = float(word)
                word = next(word_iter, '')
            except ValueError:
                self.amount = 1
            if word + 's' in UNITS:
                word += 's'
            if word not in UNITS:
                raise ValueError('`%s` is not a valid unit' % word)
            self.unit = word
            word = next(word_iter)
            if word == 'on':
                if self.unit != 'weeks':
                    raise ValueError('`on` may only be specified when the unit is weeks')
                if int(self.amount) != self.amount:
                    raise ValueError('week quantity must be an integer when `at` is specified')
                word = next(word_iter, '')
                try:
                    self.on_day = datetime.strptime(word, '%A').weekday()
                except ValueError:
                    raise ValueError('`%s` is not a valid weekday' % word)
                word = next(word_iter)
            if word == 'at':
                if self.unit not in ['days', 'weeks']:
                    raise ValueError('can only specify `at` when unit is days or weeks')
                if int(self.amount) != self.amount:
                    raise ValueError('%s quantity must be an integer when `at` is specified' % self.unit)
                # Try to get the next two words, since this is the last parameter and they might have am/pm
                word = next(word_iter, '') + ' ' + next(word_iter, '')
                # Try parsing with AM/PM first, then 24 hour time
                try:
                    self.at_time = datetime.strptime(word, '%I:%M %p')
                except ValueError:
                    try:
                        self.at_time = datetime.strptime(word, '%H:%M')
                    except ValueError:
                        raise ValueError('invalid time `%s`' % word)
            else:
                raise ValueError('`%s` is unrecognized in the schedule string' % word)
            try:
                word = next(word_iter)
                raise ValueError('`%s` is unrecognized in the schedule string' % word)
            except StopIteration:
                pass
        except StopIteration:
            pass
        if not result.get('unit') or not result.get('amount'):
            raise ValueError('must specify at least unit and interval')
        return result

