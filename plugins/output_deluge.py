import logging
import time
from deluge.ui.client import sclient

__pychecker__ = 'unusednames=parser'

log = logging.getLogger('deluge')

class OutputDeluge:

    """
        Add the torrents directly to deluge, supporting custom save paths.
    """
    
    """def __init__(self):
        self.torrent_ids = []
        self.torrent_status = []
        self.newtorrentids = []
        aclient.set_core_uri()"""
        
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
        
    def feed_output(self, feed):
        """Add torrents to deluge at exit."""
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
            sclient.add_torrent_url(entry['url'],opts)
            log.info("%s torrent added to deluge with options %s" % (entry['url'], opts))
            if config['movedone'] or config['label']:
                time.sleep(5)
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
                