from __future__ import unicode_literals, division, absolute_import
import logging
import random
import string

from flexget.entry import Entry
from flexget.plugin import register_plugin

log = logging.getLogger('gen_series')

PER_RUN = 50


class GenSeries(object):
    """
    Purely for debugging purposes. Not great quality :)

    gen_series_data:
        series: NUM
        seasons: NUM
        episodes: NUM
        qualities:
          - LIST

    This will also auto configure series plugin for testing
    """

    def __init__(self):
        self.entries = []

    def validator(self):
        from flexget import validator
        container = validator.factory('any')
        return container

    def on_process_start(self, task, config):
        log.info('Generating test data ...')
        series = []
        for num in range(config['series']):
            series.append('series %d name' % num)
            for season in range(int(config['seasons'])):
                for episode in range(int(config['episodes'])):
                    for quality in config['qualities']:
                        entry = Entry()
                        entry['title'] = 'series %d name - S%02dE%02d - %s' % \
                            (num, season + 1, episode + 1, quality)
                        entry['url'] = 'http://localhost/mock/%s' % \
                                       ''.join([random.choice(string.letters + string.digits) for x in range(1, 30)])
                        self.entries.append(entry)
        log.info('Generated %d entries' % len(self.entries))

        # configure series plugin, bad way but this is debug shit
        task.config['series'] = series

    def on_task_input(self, task, config):
        entries = []
        for num, entry in enumerate(self.entries):
            entries.append(entry)
            if num == PER_RUN - 1:
                break
        self.entries = self.entries[len(entries):]
        return entries

    def on_task_exit(self, task, config):
        if self.entries:
            log.info('There are still %d left to be processed!' % len(self.entries))
            # rerun ad infinitum, also commits session between them
            task._rerun = True
            task._rerun_count = 0


register_plugin(GenSeries, 'gen_series_data', api_ver=2, debug=True)
