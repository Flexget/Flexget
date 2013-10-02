from __future__ import unicode_literals, division, absolute_import
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

    def on_task_metainfo(self, task, config):
        # check if disabled (value set to false)
        if config is False:
            return
        for entry in task.entries:
            entry.register_lazy_fields(['quality'], self.lazy_loader)

    def lazy_loader(self, entry, field):
        self.get_quality(entry)
        return entry.get(field)

    def get_quality(self, entry):
        if entry.get('quality', eval_lazy=False):
            log.debug('Quality is already set to %s for %s, skipping quality detection.' %
                      (entry['quality'], entry['title']))
            return
        quality = qualities.Quality()
        for field_name in ['title', 'description']:
            if field_name not in entry:
                continue
            quality = qualities.Quality(entry[field_name])
            if quality:
                # if we find a quality in this field, stop searching
                break
        entry['quality'] = quality
        if quality:
            log.trace('Found quality %s (%s) for %s from field %s' %
                (entry['quality'], quality, entry['title'], field_name))


@event('plugin.register')
def register_plugin():
    plugin.register(MetainfoQuality, 'metainfo_quality', api_ver=2, builtin=True)
