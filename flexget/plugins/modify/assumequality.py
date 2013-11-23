from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.plugin import register_plugin, priority

log = logging.getLogger('assumequality')


class AssumeQuality(object):
    """
    Applies a specified quality to entries that don't have a quality set.

    Example:
    assumequality: 720p
    """

    schema = {'type': 'string', 'format': 'quality'}

    @priority(127)  #run after metainfo_quality@128
    def on_task_metainfo(self, task, quality):
        for entry in task.entries:
            if not entry.get('quality'):
                log.info("Assuming quality for %s is %s", entry['title'],quality)
                entry['quality'] = quality
                entry['assumedquality'] = True
                continue

register_plugin(AssumeQuality, 'assumequality', api_ver=2)
