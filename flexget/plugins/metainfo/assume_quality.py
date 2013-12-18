from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.plugin import register_plugin, priority, PluginError

import flexget.utils.qualities as qualities

log = logging.getLogger('assume_quality')


class AssumeQuality(object):
    """
    Applies specified quality components to entries that don't have them set.

    Example:
    assume_quality: 1080p webdl 10bit truehd
    """

#    schema = {'type': 'string', 'format': 'quality'}
    schema = {
        'oneOf': [
            {'title':'simple config', 'type': 'string', 'format': 'quality'},
            {'title':'advanced config', 'type': 'object', 'properties': {
                           'target': {'type': 'string', 'format': 'quality'},
                           'quality': {'type': 'string', 'format': 'quality'}
                           }
            }
        ]
    }

    def assume(self, entry, quality):
        newquality = qualities.Quality()
        log.verbose('%s', entry['title'])
        log.debug('Current qualities: %s', entry.get('quality'))
        for component in entry.get('quality').components:
            qualitycomponent = getattr(quality, component.type)
            log.debug('\t%s: %s vs %s', component.type, component.name, qualitycomponent.name)
            if component.name != 'unknown':
                log.debug('\t%s: keeping %s', component.type, component.name)
                setattr(newquality, component.type, component)
            elif qualitycomponent.name != 'unknown':
                log.debug('\t%s: assuming %s', component.type, qualitycomponent.name)
                setattr(newquality, component.type, qualitycomponent)
                entry['assumed_quality'] = True
            elif component.name == 'unknown' and qualitycomponent.name == 'unknown':
                log.debug('\t%s: got nothing', component.type)
        entry['quality'] = newquality
        log.verbose('New quality: %s', entry.get('quality'))

    def on_task_start(self, task, config):
        if isinstance(config, basestring): config = {'everything': config}
        self.assumptions = {}
        defaultassumption = {}
        for target, quality in config.items():
            log.verbose('New assumption: %s is %s' % (target, quality))
            #How to handle duplicates? PluginError _after_ testing?
            if target.lower() == 'everything':  #'everything' seems to be as good a default flag as any.
                try: quality = qualities.get(quality)
                except:
                    log.error('%s is not a valid quality. Forgetting assumption.' % quality)
                    continue
                defaultassumption['everything'] = quality
            else:
                try: target = qualities.Requirements(target)
                except:
                    log.error('%s is not a valid quality. Forgetting assumption.' % target)
                    continue
                try: quality = qualities.get(quality)
                except:
                    log.error('%s is not a valid quality. Forgetting assumption.' % quality)
                    continue
                self.assumptions[target] = quality
        self.assumptions.update(defaultassumption)
        for target, quality in self.assumptions.items():
            log.info('Assuming %s is %s' % (target, quality))

    @priority(127)  #run after metainfo_quality@128
    def on_task_metainfo(self, task, config):
        for entry in task.entries:
            for target, quality in self.assumptions.items():
                # if target.allows(entry['quality']) or target == everything: assume(entry,quality)
                if target == 'everything':
                    self.assume(entry, quality)

register_plugin(AssumeQuality, 'assume_quality', api_ver=2)
