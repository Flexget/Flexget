from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.plugin import register_plugin, priority

import flexget.utils.qualities as qualities

log = logging.getLogger('assume_quality')


class AssumeQuality(object):
    """
    Applies specified quality components to entries that don't have them set.

    Example:
    assume_quality: 1080p webdl 10bit truehd
    """

    schema = {'type': 'string', 'format': 'quality'}

    @priority(127)  #run after metainfo_quality@128
    def on_task_metainfo(self, task, quality):
        quality = qualities.get(quality)    #turn incoming quality into Quality object
        log.debug("Assuming quality: %s", quality)
        for entry in task.entries:
            newquality = qualities.Quality()
            log.verbose("%s", entry['title'])
            log.debug("Current qualities: %s", entry.get('quality'))
            for component in entry.get('quality').components:
                qualitycomponent = getattr(quality, component.type)
                log.debug("\t%s: %s vs %s", component.type, component.name, qualitycomponent.name)
                if component.name != "unknown":
                    log.debug("\t%s: keeping %s", component.type, component.name)
                    setattr(newquality, component.type, component)
                elif qualitycomponent.name != "unknown":
                    log.debug("\t%s: assuming %s", component.type, qualitycomponent.name)
                    setattr(newquality, component.type, qualitycomponent)
                    entry['assumed_quality'] = True
                elif component.name == "unknown" and qualitycomponent.name == "unknown":
                    log.debug("\t%s: got nothing", component.type)
            entry['quality'] = newquality
            log.verbose("New quality: %s", entry.get('quality'))

register_plugin(AssumeQuality, 'assume_quality', api_ver=2)
