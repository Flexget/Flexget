import logging
import time, os, sys
from flexget.manager import PluginError, Base
from sqlalchemy import Column, Integer, String
from sqlalchemy.schema import ForeignKey
from sqlalchemy.orm import relation,join

log = logging.getLogger('deluge')

class DelugeEpisode(Base):
    
    __tablename__ = 'deluge_episodes'

    id = Column(Integer, primary_key=True)
    
    torrentid = Column(Integer)
    episode_id = Column(Integer, ForeignKey('series_episodes.id'))

    def __repr__(self):
        return '<DelugeEpisode(identifier=%s)>' % (self.identifier)

class OutputDeluge:

    """
        Add the torrents directly to deluge, supporting custom save paths.
    """

    def __init__(self):
        pass

    def register(self, manager, parser):
        manager.register('deluge', output_priority=1)

    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('boolean')
        deluge = root.accept('dict')
        deluge.accept('text', key='path')
        deluge.accept('text', key='movedone')
        deluge.accept('text', key='label')
        deluge.accept('boolean', key='queuetotop')
        deluge.accept('boolean', key='enabled')
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
            raise PluginError('Deluge module required', log)
        config = self.get_config(feed)

        # don't add when learning
        if feed.manager.options.learn:
            return
        if not feed.accepted or not config['enabled']:
            return

        sclient.set_core_uri()
        opts = {}
        for entry in feed.accepted:
            try:
                before = sclient.get_session_state()
            except Exception, (errno, msg):
                raise PluginError('Could not communicate with deluge core. %s' % msg, log)

            path = entry.get('path', config['path'])
            if 'path':
                opts['download_location'] = path % entry
            # see that temp file is present
            if not os.path.exists(entry['file']):
                tmp_path = os.path.join(feed.manager.config_base, 'temp')
                log.debug('entry: %s' % entry)
                log.debug('temp: %s' % ', '.join(os.listdir(tmp_path)))
                raise PluginError("Downloaded temp file '%s' doesn't exist!?" % entry['file'], log)
            sclient.add_torrent_file([entry['file']], [opts])
            log.info("%s torrent added to deluge with options %s" % (entry['title'], opts))

            #clean up temp file if download plugin is not configured for this feed
            if not 'download' in feed.config:
                os.remove(entry['file'])
                del(entry['file'])
            movedone = entry.get('movedone', config['movedone'])
            label = entry.get('label', config['label']).lower()
            queuetotop = entry.get('queuetotop', config['queuetotop'])
            #if not any([movedone, label, queuetotop]):
            #    continue
            time.sleep(1)
            after = sclient.get_session_state()
            for item in after:
                #find torrentid of just added torrent
                if not item in before:
                    entry['deluge_torrentid'] = item
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
            else:
                log.info("%s is already loaded in deluge. Cannot change label, movedone, or queuetotop" % entry['title'])
    #TODO: Activate once propers are detected or another use is thought of.
    """
    def feed_exit(self, feed):
        #Remember torrentid of series torrents for future control
        for entry in feed.accepted:
            if not 'deluge_torrentid' in entry:
                continue
            parser = entry.get('series_parser')
            if parser:
                from filter_series import Episode, Series
                log.debug('storing deluge torrentid for %s' % parser)
                episode = feed.session.query(Episode).select_from(join(Episode, Series)).\
                    filter(Series.name==parser.name).filter(Episode.identifier==parser.identifier()).first()
                if episode:
                    # if does not exist in database, add new
                    delugeepisode = feed.session.query(DelugeEpisode).filter(DelugeEpisode.episode_id==episode.id).first()
                    if not delugeepisode:
                        delugeepisode = DelugeEpisode()
                        delugeepisode.episode_id = episode.id
                        delugeepisode.torrentid = entry['deluge_torrentid']
                        feed.session.add(delugeepisode)
    """
