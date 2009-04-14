import logging
import mimetypes
from manager import PluginWarning

__pychecker__ = 'unusednames=parser'

log = logging.getLogger('path_by_ext')

class PluginPathByExt:

    """
    path_by_ext:
      torrent: ~/watch/torrents/
      nzb: ~/watch/nzbs/
    """

    def register(self, manager, parser):
        manager.register('path_by_ext')
        
    def validator(self):
        import validator
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
            if 'mime' in entry:
                # check if configuration has mimetype that entry has
                if entry['mime'] in config:
                    callback(entry, config[entry['mime']])
                # check if entry mimetype extension matches in config
                ext = mimetypes.types_map.get(entry['mime'])
                path = config.get(ext) or config.get(ext[1:])
                if path:
                    callback(entry, path)
                else:
                    log.debug('Unknown mimetype %s' % entry['mime'])
            else:
                # try to find from url
                for ext, path in config.iteritems():
                    if entry['url'].endswith('.'+ext):
                        callback(entry, path)