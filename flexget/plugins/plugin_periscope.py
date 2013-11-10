import logging
import os
import periscope
import tempfile

from flexget.plugin import register_plugin

log = logging.getLogger('subtitles')
psc = periscope.Periscope(tempfile.gettempdir())

# should this stuff be in config?
EXTVID = ['.avi', '.mp4', '.mkv']
EXTSUB = ['.srt']

# to avoid A LOT of info/warnings/errors coming from periscope:
logging.getLogger("periscope").setLevel(logging.CRITICAL)


class PluginPeriscope(object):
    """
    Search and download subtitles for all the video files in a given path.
    (it uses Periscope by Patrick Dessalle, http://code.google.com/p/periscope/)

    Example::
    
      periscope:
        path: d:\media\series
        languages:
          - it
          - en
        overwrite: no
    
    With overwrite=no the plugin will ignore video with associated subtitles.
    """
    
    schema = {
        'type': 'object',
        'properties': {
            'path': {'type': 'string', 'format': 'path'},
            'languages': {"type": "array", "items": {"type": "string"}},
            'overwrite': {'type': 'boolean', 'default': False}
        },
        'additionalProperties': False
    }
    
    def check_file(self, filename):
        if not (os.path.splitext(filename)[1] in EXTVID):
            return
        if not self.overwrite:
            for s in EXTSUB:
                if os.path.exists(os.path.splitext(filename)[0] + s):
                    return
        if psc.downloadSubtitle(filename.encode("utf8"), self.langs):
            log.info('Subtitles found for %s' % filename)
    
    def on_task_start(self, task, config):
        """Download subtitles using Periscope"""
        self.overwrite = config['overwrite']
        # just to avoid some UnicodeWarning in periscope:
        self.langs = []
        for u in config['languages']:
            self.langs.append(u.encode('utf8'))
        # scanning path
        for root, dirs, files in os.walk(config['path']):
            if '$RECYCLE.BIN' in root:  # Windows weird stuff
                continue
            for video in files:
                self.check_file(os.path.join(root, video))

register_plugin(PluginPeriscope, 'periscope', api_ver=2)
