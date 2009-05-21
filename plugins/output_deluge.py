import logging
import time, os, sys
from manager import PluginError, PluginWarning

log = logging.getLogger('deluge')

class OutputDeluge:

    """
        Add the torrents directly to deluge, supporting custom save paths.
    """
    
    def register(self, manager, parser):
        manager.register('deluge')

    def validator(self):
        import validator
        deluge = validator.factory('dict')
        deluge.accept('text', key='path')
        deluge.accept('text', key='movedone')
        deluge.accept('text', key='label')
        return deluge
        
    def get_config(self, feed):
        config = feed.config['deluge']
        config.setdefault('path', '')
        config.setdefault('movedone', '')
        config.setdefault('label', '')
        if config['label']:
            config['label'] = str(config['label']).lower()
        return config
        
    def feed_download(self, feed):
        """
        call the feed_download method of download plugin
        this will generate the temp files we will load into deluge
        we don't need to call this if download plugin is loaded on this feed
        """
        if not 'download' in feed.config:
            download = feed.manager.get_plugin_by_name('download')
            download['instance'].feed_download(feed)
        
    def feed_output(self, feed):
        """Add torrents to deluge at exit."""
        try:
            from deluge.ui.client import sclient
        except:
            raise PluginError('Deluge module required')
        config = self.get_config(feed)
        
		# don't add when learning
        if feed.manager.options.learn:
            return
        if not feed.accepted:
            return
        sclient.set_core_uri()
        opts = {}
        for entry in feed.accepted:
            if config['movedone'] or config['label']:
                before = sclient.get_session_state()
            if 'path' in entry:
                opts['download_location'] = entry['path']
            elif config['path']:
                opts['download_location'] = str(config['path'])
            # see that temp file is present
            if not os.path.exists(entry['file']):
                tmp_path = os.path.join(sys.path[0], 'temp')
                log.debug('entry: %s' % entry)
                log.debug('temp: %s' % ', '.join(os.listdir(tmp_path)))
                raise PluginWarning("Downloaded temp file '%s' doesn't exist!?" % entry['file'])
            
            sclient.add_torrent_file([entry['file']], [opts])
            
            #clean up temp file if download plugin is not configured for this feed
            if not feed.config.has_key('download'):
                os.remove(entry['file'])
                del(entry['file'])
            
            log.info("%s torrent added to deluge with options %s" % (entry['title'], opts))
            if config['movedone'] or config['label']:
                time.sleep(4)
                after = sclient.get_session_state()
                for item in after:
                    if not item in before:
                        if config['movedone']:
                            sclient.set_torrent_move_on_completed(item, True)
                            sclient.set_torrent_move_on_completed_path(item, str(config['movedone']) % entry)
                        if config['label']:
                            if not "label" in sclient.get_enabled_plugins():
                                sclient.enable_plugin("label")
                            if not config['label'] in sclient.label_get_labels():
                                sclient.label_add(config['label'])
                            sclient.label_set_torrent(item, config['label'])
                        break
                