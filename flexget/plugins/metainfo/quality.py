from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.utils import qualities

log = logging.getLogger('metainfo_quality')


class MetainfoQuality(object):
    """
    Utility:

    Set quality attribute for entries.
    """

    schema = {'type': 'boolean'}

    @plugin.priority(127)  # Run after other plugins that might fill quality (series)
    def on_task_metainfo(self, task, config):
        # check if disabled (value set to false)
        if config is False:
            return
        for entry in task.entries:
            entry.register_lazy_func(self.get_quality, ['quality'])

    def get_quality(self, entry):
        if entry.get('quality', eval_lazy=False):
            log.debug('Quality is already set to %s for %s, skipping quality detection.' %
                      (entry['quality'], entry['title']))
            return
        entry['quality'] = qualities.Quality(entry['title'])
        if entry['quality']:
            log.trace('Found quality %s for %s' % (entry['quality'], entry['title']))


@event('plugin.register')
def register_plugin():
    plugin.register(MetainfoQuality, 'metainfo_quality', api_ver=2, builtin=True)
