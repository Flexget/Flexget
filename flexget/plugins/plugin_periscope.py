import logging
import os
import periscope
import tempfile
import urllib

from flexget.plugin import register_plugin

log = logging.getLogger('subtitles')
psc = periscope.Periscope(tempfile.gettempdir())

# should this stuff be in config?
EXTSUB = ['.srt']

# to avoid A LOT of info/warnings/errors coming from periscope:
logging.getLogger("periscope").setLevel(logging.CRITICAL)


class PluginPeriscope(object):
    """
    Search and download subtitles using Periscope by Patrick Dessalle 
    (http://code.google.com/p/periscope/).
    It process only accepted entries referred to local files, and it can be 
    instructed to ignore (not overwrite) video already associated with subtitles.
    
    Example::
    
      periscope:
        languages:
          - it
          - en
        overwrite: no
    
    Example (complete task)::

      subs:
        find:
          path: 
            - d:\media\incoming
          regexp: '.*\.(avi|mkv|mp4)$'
          recursive: yes
        accept_all: yes
        periscope:
          languages:
            - it
            - en
    """
    
    schema = {
        'type': 'object',
        'properties': {
            'languages': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1},
            'overwrite': {'type': 'boolean', 'default': False}
        },
        'additionalProperties': False
    }
    
    def subbed(self, filename):
        for ext in EXTSUB:
            if os.path.exists(os.path.splitext(filename)[0] + ext):
                return True
        return False
    
    def on_task_output(self, task, config):
        if not task.accepted:
            log.debug('nothing accepted, aborting')
            return
        langs = []
        for u in config['languages']:
            langs.append(u.encode('utf8'))  # unicode warnings in periscope
        for entry in task.accepted:
            if not 'location' in entry:
                entry.reject('is not a local file')
                continue
            if '$RECYCLE.BIN' in entry['location']:  # happens in connected network shares
                entry.reject("is in Windows recycle-bin")
            elif not os.path.exists(entry['location']):
                entry.reject('file not found')  # periscope works on hashes
            elif not config['overwrite'] and self.subbed(entry['location']):
                entry.reject('cannot overwrite existing subs')
            elif psc.downloadSubtitle(entry['location'].encode("utf8"), langs):
                log.info('Subtitles found for %s' % entry['location'])
            else:
                entry.reject('cannot find subtitles for now.')


register_plugin(PluginPeriscope, 'periscope', api_ver=2)
