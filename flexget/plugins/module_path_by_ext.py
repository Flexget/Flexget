import logging
import mimetypes
from flexget.plugin import *

log = logging.getLogger('path_by_ext')

class PluginPathByExt:
    """
    path_by_ext:
      torrent: ~/watch/torrent/
      nzb: ~/watch/nzb/
    """

    def validator(self):
        from flexget import validator
        config = validator.factory('dict')
        config.accept_any_key('any')
        return config

    def feed_modify(self, feed):
        self.ext(feed, self.set_path)

    def set_path(self, entry, path):
        log.debug('Setting %s path to %s' % (entry['title'], path))
        entry['path'] = path    
    
    def ext(self, feed, callback):
        config = feed.config
        for entry in feed.entries:
            if 'mime-type' in entry:
                # check if configuration has mimetype that entry has
                if entry['mime-type'] in config:
                    callback(entry, config[entry['mime-type']])
                # check if entry mimetype extension matches in config
                ext = mimetypes.types_map.get(entry['mime-type'])
                path = config.get(ext) or config.get(ext[1:])
                if path:
                    callback(entry, path)
                else:
                    log.debug('Unknown mimetype %s' % entry['mime-type'])
            else:
                # try to find from url
                for ext, path in config.iteritems():
                    if entry['url'].endswith('.'+ext):
                        callback(entry, path)

register_plugin(PluginPathByExt, 'path_by_ext')
