import logging
import os
import tempfile

from loguru import logger

from flexget import entry, plugin
from flexget.event import event

logger = logger.bind(name='check_subtitles')


class MetainfoSubs:
    """
    Set 'subtitles' field for entries, if they are local video files with subs.
    The field is a list of language codes (3-letter ISO-639-3) for each subtitles
    file found on disk and/or subs track found inside video (for MKVs).
    Special "und" code is for unidentified language (i.e. files without language
    code before extension).
    """

    schema = {'type': 'boolean'}

    def on_task_start(self, task, config):
        try:
            import subliminal
        except ImportError as e:
            logger.debug('Error importing Subliminal: {}', e)
            raise plugin.DependencyError(
                'subliminal', 'subliminal', 'Subliminal module required. ImportError: %s' % e
            )
        from dogpile.cache.exception import RegionAlreadyConfigured
        from subliminal.cli import MutexLock

        try:
            subliminal.region.configure(
                'dogpile.cache.dbm',
                arguments={
                    'filename': os.path.join(tempfile.gettempdir(), 'cachefile.dbm'),
                    'lock_factory': MutexLock,
                },
            )
        except RegionAlreadyConfigured:
            pass
        logging.getLogger("subliminal").setLevel(logging.CRITICAL)
        logging.getLogger("enzyme").setLevel(logging.WARNING)

    def on_task_metainfo(self, task, config):
        # check if explicitly disabled (value set to false)
        if config is False:
            return
        for entry in task.entries:
            entry.add_lazy_fields(self.get_subtitles, ['subtitles'])

    @entry.register_lazy_lookup('subtitles_check')
    def get_subtitles(self, entry):
        if (
            entry.get('subtitles', eval_lazy=False)
            or not ('location' in entry)
            or ('$RECYCLE.BIN' in entry['location'])
            or not os.path.exists(entry['location'])
        ):
            return
        from subliminal import scan_video
        from subliminal.core import refine, search_external_subtitles

        try:
            video = scan_video(entry['location'])
            # grab external and internal subtitles
            subtitles = video.subtitle_languages
            refiner = ('metadata',)
            refine(video, episode_refiners=refiner, movie_refiners=refiner)
            subtitles |= set(search_external_subtitles(entry['location']).values())
            if subtitles:
                # convert to human-readable strings
                subtitles = [str(l) for l in subtitles]
                entry['subtitles'] = subtitles
                logger.debug('Found subtitles {} for {}', '/'.join(subtitles), entry['title'])
        except Exception as e:
            logger.error('Error checking local subtitles for {}: {}', entry['title'], e)


@event('plugin.register')
def register_plugin():
    plugin.register(MetainfoSubs, 'check_subtitles', api_ver=2)
