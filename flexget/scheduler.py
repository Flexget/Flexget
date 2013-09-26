from __future__ import unicode_literals, division, absolute_import
from datetime import datetime, timedelta
import functools

UNITS = ['seconds', 'minutes', 'hours', 'days', 'weeks']


# format: every NUM UNIT [on WEEKDAY] [at TIME]
def parse_schedule_text(text):
    result = {}
    word_iter = iter(text.lower().split(' '))
    try:
        if next(word_iter, '') != 'every':
            raise ValueError('schedule string must start with `every`')
        word = next(word_iter)
        try:
            result['amount'] = float(word)
            word = next(word_iter)
        except ValueError:
            result['amount'] = 1
        if word + 's' in UNITS:
            word += 's'
        if word not in UNITS:
            raise ValueError('`%s` is not a valid unit' % word)
        result['unit'] = word
        word = next(word_iter)
        if word == 'on':
            if result['unit'] != 'weeks':
                raise ValueError('`on` may only be specified when the unit is weeks')
            if int(result['amount']) != result['amount']:
                raise ValueError('week quantity must be an integer when `at` is specified')
            word = next(word_iter, None)
            try:
                result['on_day'] = datetime.strptime(word, '%A').weekday()
            except ValueError:
                raise ValueError('`%s` is not a valid weekday' % word)
            word = next(word_iter)
        if word == 'at':
            if result['unit'] not in ['days', 'weeks']:
                raise ValueError('can only specify `at` when unit is days or weeks')
            if int(result['amount']) != result['amount']:
                raise ValueError('%s quantity must be an integer when `at` is specified' % result['unit'])
            # Try to get the next two words, since this is the last parameter and they might have am/pm
            word = next(word_iter, '') + ' ' + next(word_iter, '')
            # Try parsing with AM/PM first, then 24 hour time
            try:
                result['at_time'] = datetime.strptime(word, '%I:%M %p')
            except ValueError:
                try:
                    result['at_time'] = datetime.strptime(word, '%H:%M')
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


class Job(object):
    def __init__(self):
        self.job_func = None
        self.unit = None
        self.amount = None
        self.on_day = None
        self.at_time = None
        self.last_run = None
        self.next_run = None

    @property
    def should_run(self):
        return datetime.datetime.now() >= self.next_run

    @property
    def period(self):
        return datetime.timedelta(**{self.unit: self.amount})

    # TODO: How should it work when a specific day and or time was given, but it's been longer than the interval since
    # we ran last? Wait for the next specified day/time, or run now, because we missed one?
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

