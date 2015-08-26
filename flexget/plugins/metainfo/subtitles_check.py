from __future__ import unicode_literals, division, absolute_import
import logging
import os
import tempfile

from flexget import plugin
from flexget.event import event

log = logging.getLogger('check_subtitles')


class MetainfoSubs(object):
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
            log.debug('Error importing Subliminal: %s' % e)
            raise plugin.DependencyError('subliminal', 'subliminal', 
                'Subliminal module required. ImportError: %s' % e)
        from subliminal.cli import MutexLock
        from dogpile.cache.exception import RegionAlreadyConfigured
        try:
            subliminal.region.configure('dogpile.cache.dbm', 
                arguments={'filename': os.path.join(tempfile.gettempdir(), 'cachefile.dbm'), 
                           'lock_factory': MutexLock})
        except RegionAlreadyConfigured:
            pass
        logging.getLogger("subliminal").setLevel(logging.CRITICAL)
        logging.getLogger("enzyme").setLevel(logging.WARNING)

    def on_task_metainfo(self, task, config):
        # check if explicitly disabled (value set to false)
        if config is False:
            return
        for entry in task.entries:
            entry.register_lazy_func(self.get_subtitles, ['subtitles'])

    def get_subtitles(self, entry):
        if entry.get('subtitles', eval_lazy=False) or not ('location' in entry) or \
                ('$RECYCLE.BIN' in entry['location']) or not os.path.exists(entry['location']):
            return
        import subliminal
        try:
            video = subliminal.scan_video(entry['location'])
            lst = [l.alpha3 for l in video.subtitle_languages]
            if lst:
                entry['subtitles'] = lst
                log.trace('Found subtitles %s for %s' % ('/'.join(lst), entry['title']))
        except Exception as e:
            log.debug('Error checking local subtitles for %s: %s' % (entry['title'], e))


@event('plugin.register')
def register_plugin():
    plugin.register(MetainfoSubs, 'check_subtitles', api_ver=2)
