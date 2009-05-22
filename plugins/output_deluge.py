import logging
import time, os, sys
from manager import PluginError, PluginWarning

log = logging.getLogger('deluge')

class OutputDeluge:

    """
        Add the torrents directly to deluge, supporting custom save paths.
    """
    
    def __init__(self):
        pass
    
    def register(self, manager, parser):
        manager.register('deluge')

    def validator(self):
        import validator
        root = validator.factory()
        root.accept('boolean')
        deluge = root.accept('dict')
        deluge.accept('text', key='path')
        deluge.accept('text', key='movedone')
        deluge.accept('text', key='label')
        deluge.accept('boolean', key='queuetotop')
        return root
        
    def get_config(self, feed):
        config = feed.config.get('deluge', {})
        if isinstance(config, bool):
            config = {'enabled':config}
        config.setdefault('enabled', True)
        config.setdefault('path', '')
        config.setdefault('movedone', '')
        config.setdefault('label', '')
        config.setdefault('queuetotop', False)
        return config
        
    def feed_start(self, feed):
        """
        register the usable set: keywords
        """
        set = feed.manager.get_plugin_by_name('set')
        set['instance'].register_keys({'path':'text', 'movedone':'text', 'queuetotop':'boolean', 'label':'text'})
        
    def feed_download(self, feed):
        """
        call the feed_download method of download plugin
        this will generate the temp files we will load into deluge
        we don't need to call this if download plugin is loaded on this feed
        """
        config = self.get_config(feed)
        if not config['enabled']:
            return
        if not 'download' in feed.config:
            download = feed.manager.get_plugin_by_name('download')
            """Download all feed content and store in temporary folder"""
            for entry in feed.accepted:
                try:
                    if feed.manager.options.test:
                        log.info('Would download: %s' % entry['title'])
                    else:
                        if not feed.manager.unit_test:
                            log.info('Downloading: %s' % entry['title'])
                        download['instance'].download(feed, entry)
                except IOError, e:
                    feed.fail(entry)
                    if hasattr(e, 'reason'):
                        log.error('Failed to reach server. Reason: %s' % e.reason)
                    elif hasattr(e, 'code'):
                        log.error('The server couldn\'t fulfill the request. Error code: %s' % e.code)

        
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
        if not feed.accepted or not config['enabled']:
            return
        sclient.set_core_uri()
        opts = {}
        for entry in feed.accepted:
            before = sclient.get_session_state()
            path = entry.get('path', config['path'])
            if 'path':
                opts['download_location'] = path % entry
            # see that temp file is present
            if not os.path.exists(entry['file']):
                tmp_path = os.path.join(sys.path[0], 'temp')
                log.debug('entry: %s' % entry)
                log.debug('temp: %s' % ', '.join(os.listdir(tmp_path)))
                raise PluginWarning("Downloaded temp file '%s' doesn't exist!?" % entry['file'])
            
            sclient.add_torrent_file([entry['file']], [opts])
            log.info("%s torrent added to deluge with options %s" % (entry['title'], opts))
            
            #clean up temp file if download plugin is not configured for this feed
            if not feed.config.has_key('download'):
                os.remove(entry['file'])
                del(entry['file'])

            time.sleep(1)
            after = sclient.get_session_state()
            movedone = entry.get('movedone', config['movedone'])
            label = entry.get('label', config['label']).lower()
            queuetotop = entry.get('queuetotop', config['queuetotop'])
            for item in after:
                if not item in before:
                    if movedone:
                        log.info("%s move on complete set to %s" % (entry['title'], movedone % entry))
                        sclient.set_torrent_move_on_completed(item, True)
                        sclient.set_torrent_move_on_completed_path(item, movedone % entry)
                    if label:
                        if not "label" in sclient.get_enabled_plugins():
                            sclient.enable_plugin("label")
                        if not label in sclient.label_get_labels():
                            sclient.label_add(label)
                        log.info("%s label set to '%s'" % (entry['title'], label))
                        sclient.label_set_torrent(item, label)
                    if queuetotop:
                        log.info("%s moved to top of queue" % entry['title'])
                        sclient.queue_top([item])
                    break
                