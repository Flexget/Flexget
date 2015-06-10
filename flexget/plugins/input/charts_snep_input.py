from __future__ import unicode_literals, division, absolute_import
import logging
from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.charts_snep import SnepChartsParser, SnepParsedChartEntry
from flexget.utils.cached_input import cached

log = logging.getLogger('charts_snep_input')



class ChartsSnepInput(object):
    """Create an entrie for each charted single in your charts request"""

    schema = {
        'type': {
            'type': 'string',
            'enum': ['all_album', 'disk_album', 'digit_album',
                     'digit_single', 'stream_single',
                     'compil', 'back_catalog', 'radio']
        }
    }



    @cached('charts_snep_input', persist='2 hours')
    def on_task_input(self, task, config):
        log.verbose('Retrieving weekly SNEP charts of %s' % config)
        parser = SnepChartsParser()
        chart_entries = parser.retrieve_charts(config)
        """:type chart_entries: list of [flexget.utils.charts_snep.SnepParsedChartEntry]"""

        input_entries = []
        for charts_entry in chart_entries:
            flexget_entry = Entry()
            flexget_entry['title'] = "%s - %s" % (charts_entry.artist, charts_entry.recording_title)
            flexget_entry.update_using_map(SnepParsedChartEntry.get_entry_map(), charts_entry)
            input_entries.append(flexget_entry)

        return input_entries

@event('plugin.register')
def register_plugin():
    plugin.register(ChartsSnepInput, 'charts_snep_input', api_ver=2)
