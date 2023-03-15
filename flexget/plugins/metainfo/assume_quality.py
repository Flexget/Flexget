from collections import namedtuple

from loguru import logger

import flexget.utils.qualities as qualities
from flexget import plugin
from flexget.event import event

logger = logger.bind(name='assume_quality')


class AssumeQuality:
    """
    Applies quality components to entries that match specified quality requirements.
    When a quality is applied, any components which are unknown in the entry are filled from the applied quality.
    Quality requirements are tested in order of increasing precision (ie "720p h264" is more precise than "1080p"
    so gets tested first), and applied as matches are found. Using the simple configuration is the same as specifying
    an "any" rule.

    Examples::
    assume_quality: 1080p webdl 10bit truehd

    assume_quality:
      hdtv: 720p
      720p hdtv: 10bit
      '!ac3 !mp3': flac
      any: 720p h264
    """

    schema = {
        'oneOf': [
            {'title': 'simple config', 'type': 'string', 'format': 'quality'},
            {
                'title': 'advanced config',
                'type': 'object',
                # Can't validate dict keys, so allow any
                'additionalProperties': {'type': 'string', 'format': 'quality'},
            },
        ]
    }

    def precision(self, qualityreq):
        p = 0
        for component in qualityreq.components:
            if component.acceptable:
                p += 8
            if component.min:
                p += 4
            if component.max:
                p += 4
            if component.none_of:
                p += len(component.none_of)
                # Still a long way from perfect, but probably good enough.
        return p

    def assume(self, entry, quality):
        newquality = qualities.Quality()
        logger.debug('Current qualities: {}', entry.get('quality'))
        for component in entry.get('quality').components:
            qualitycomponent = getattr(quality, component.type)
            logger.debug('\t{}: {} vs {}', component.type, component.name, qualitycomponent.name)
            if component.name != 'unknown':
                logger.debug('\t{}: keeping {}', component.type, component.name)
                setattr(newquality, component.type, component)
            elif qualitycomponent.name != 'unknown':
                logger.debug('\t{}: assuming {}', component.type, qualitycomponent.name)
                setattr(newquality, component.type, qualitycomponent)
                entry['assumed_quality'] = True
            elif component.name == 'unknown' and qualitycomponent.name == 'unknown':
                logger.debug('\t{}: got nothing', component.type)
        entry['quality'] = newquality
        logger.debug('Quality updated: {}', entry.get('quality'))

    def on_task_start(self, task, config):
        if isinstance(config, str):
            config = {'any': config}
        assume = namedtuple('assume', ['target', 'quality'])
        self.assumptions = []
        for target, quality in list(config.items()):
            logger.verbose('New assumption: {} is {}', target, quality)
            try:
                target = qualities.Requirements(target)
            except ValueError:
                raise plugin.PluginError(
                    '%s is not a valid quality. Forgetting assumption.' % target
                )
            try:
                quality = qualities.get(quality)
            except ValueError:
                raise plugin.PluginError(
                    '%s is not a valid quality. Forgetting assumption.' % quality
                )
            self.assumptions.append(assume(target, quality))
        self.assumptions.sort(
            key=lambda assumption: self.precision(assumption.target), reverse=True
        )
        for assumption in self.assumptions:
            logger.debug(
                'Target {} - Priority {}', assumption.target, self.precision(assumption.target)
            )

    @plugin.priority(100)  # run after other plugins which fill quality (series, quality)
    def on_task_metainfo(self, task, config):
        for entry in task.entries:
            logger.verbose(entry.get('title'))
            for assumption in self.assumptions:
                logger.debug('Trying {} - {}', assumption.target, assumption.quality)
                if assumption.target.allows(entry.get('quality')):
                    logger.debug('Match: {}', assumption.target)
                    self.assume(entry, assumption.quality)
            logger.verbose('New quality: {}', entry.get('quality'))


@event('plugin.register')
def register_plugin():
    plugin.register(AssumeQuality, 'assume_quality', api_ver=2)
