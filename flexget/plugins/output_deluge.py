import logging
import time
import os
import base64
from flexget.plugin import *

log = logging.getLogger('deluge')


class OutputDeluge:

    """
        Add the torrents directly to deluge, supporting custom save paths.
    """

    def validator(self):
        from flexget import validator
        root = validator.factory()
        root.accept('boolean')
        deluge = root.accept('dict')
        deluge.accept('text', key='host')
        deluge.accept('number', key='port')
        deluge.accept('text', key='user')
        deluge.accept('text', key='pass')
        deluge.accept('text', key='path')
        deluge.accept('text', key='movedone')
        deluge.accept('text', key='label')
        deluge.accept('boolean', key='queuetotop')
        deluge.accept('boolean', key='enabled')
        return root

    def get_config(self, feed):
        config = feed.config.get('deluge', {})
        if isinstance(config, bool):
            config = {'enabled': config}
        config.setdefault('host', 'localhost')
        config.setdefault('port', 58846)
        config.setdefault('user', '')
        config.setdefault('pass', '')
        config.setdefault('enabled', True)
        config.setdefault('path', '')
        config.setdefault('movedone', '')
        config.setdefault('label', '')
        config.setdefault('queuetotop', False)
        return config

    def on_process_start(self, feed):
        """
            register the usable set: keywords
        """
        set_plugin = get_plugin_by_name('set')
        set_plugin.instance.register_keys({'path': 'text', 'movedone': 'text', \
            'queuetotop': 'boolean', 'label': 'text'})

    def on_feed_download(self, feed):
        """
            call the feed_download method of download plugin
            this will generate the temp files we will load into deluge
            we don't need to call this if download plugin is loaded on this feed
        """
        config = self.get_config(feed)
        if not config['enabled']:
            return
        if not 'download' in feed.config:
            download = get_plugin_by_name('download')
            # download all content to temp folder, may fail some entries
            download.instance.on_feed_download(feed)

    def on_feed_output(self, feed):
        """Add torrents to deluge at exit."""
        config = self.get_config(feed)
        # don't add when learning
        if feed.manager.options.learn:
            return
        if not feed.accepted or not config['enabled']:
            return

        # TODO: Figure out better way to detect version
        try:
            from deluge.ui.client import sclient
        except:
            log.info("Using deluge 1.2 api")
            self.add_to_deluge12(feed, config)
        else:
            log.info("Using deluge 1.1 api")
            self.add_to_deluge11(feed, config)

    def add_to_deluge11(self, feed, config):
        """Add torrents to deluge at exit."""
        try:
            from deluge.ui.client import sclient
        except:
            raise PluginError('Deluge module required', log)

        sclient.set_core_uri()
        opts = {}
        for entry in feed.accepted:
            try:
                before = sclient.get_session_state()
            except Exception, (errno, msg):
                raise PluginError('Could not communicate with deluge core. %s' % msg, log)

            path = entry.get('path', config['path'])
            if path:
                opts['download_location'] = os.path.expanduser(path % entry)
            
            # check that file is downloaded
            if not 'file' in entry:
                feed.fail(entry, 'file missing?')
                continue
                
            # see that temp file is present
            if not os.path.exists(entry['file']):
                tmp_path = os.path.join(feed.manager.config_base, 'temp')
                log.debug('entry: %s' % entry)
                log.debug('temp: %s' % ', '.join(os.listdir(tmp_path)))
                raise PluginError("Downloaded temp file '%s' doesn't exist!?" % entry['file'], log)

            sclient.add_torrent_file([entry['file']], [opts])
            log.info("%s torrent added to deluge with options %s" % (entry['title'], opts))

            # clean up temp file if download plugin is not configured for this feed
            if not 'download' in feed.config:
                os.remove(entry['file'])
                del(entry['file'])

            movedone = entry.get('movedone', config['movedone'])
            label = entry.get('label', config['label']).lower()
            queuetotop = entry.get('queuetotop', config['queuetotop'])

            # Sometimes deluge takes a moment to add the torrent, wait a second.
            time.sleep(2)
            after = sclient.get_session_state()
            for item in after:
                # find torrentid of just added torrent
                if not item in before:
                    # entry['deluge_torrentid'] = item
                    if movedone:
                        log.debug("%s move on complete set to %s" % (entry['title'], movedone % entry))
                        sclient.set_torrent_move_on_completed(item, True)
                        sclient.set_torrent_move_on_completed_path(item, os.path.expanduser(movedone % entry))
                    if label:
                        if not "label" in sclient.get_enabled_plugins():
                            sclient.enable_plugin("label")
                        if not label in sclient.label_get_labels():
                            sclient.label_add(label)
                        log.debug("%s label set to '%s'" % (entry['title'], label))
                        sclient.label_set_torrent(item, label)
                    if queuetotop:
                        log.debug("%s moved to top of queue" % entry['title'])
                        sclient.queue_top([item])
                    break
            else:
                log.info("%s is already loaded in deluge. Cannot change label, movedone, or queuetotop" % entry['title'])
                
    def add_to_deluge12(self, feed, config):
        try:
            from twisted.internet import reactor, defer
            from deluge.ui.client import client
        except:
            raise PluginError('Deluge and twisted modules required', log)

        d = client.connect(
            host=config['host'],
            port=config['port'],
            username=config['user'],
            password=config['pass'])

        def on_connect_success(result):
            if not result:
                # TODO: connect failed, do something
                pass

            def on_success(torrent_id, entry, config):
                if not torrent_id:
                    log.info("%s is already loaded in deluge, cannot set movedone, label, or queuetotop." % entry['title'])
                    return
                log.info("%s successfully added to deluge." % entry['title'])
                movedone = os.path.expanduser(entry.get('movedone', config['movedone']) % entry)
                label = entry.get('label', config['label']).lower()
                queuetotop = entry.get('queuetotop', config['queuetotop'])
                if movedone:
                    if not os.path.isdir(movedone):
                        log.debug("movedone path %s doesn't exist, creating" % movedone)
                        os.makedirs(movedone)
                    log.debug("%s move on complete set to %s" % (entry['title'], movedone))
                    client.core.set_torrent_move_completed(torrent_id, True)
                    client.core.set_torrent_move_completed_path(torrent_id, movedone)
                if label:
                    # TODO: check if label plugin is enabled
                    client.label.add(label)
                    client.label.set_torrent(torrent_id, label)
                    log.debug("%s label set to '%s'" % (entry['title'], label))
                if queuetotop:
                    log.debug("%s moved to top of queue" % entry['title'])
                    client.core.queue_top([torrent_id])

            def on_fail(result, entry, feed):
                log.info("%s was not added to deluge! %s" % (entry['title'], result))
                feed.fail(entry, "Could not be added to deluge")

            # add the torrents
            dlist = []
            for entry in feed.accepted:
                opts = {}
                path = entry.get('path', config['path'])
                if path:
                    opts['download_location'] = os.path.expanduser(path % entry)
                # see that temp file is present
                if not os.path.exists(entry['file']):
                    tmp_path = os.path.join(feed.manager.config_base, 'temp')
                    log.debug('entry: %s' % entry)
                    log.debug('temp: %s' % ', '.join(os.listdir(tmp_path)))
                    raise PluginError("Downloaded temp file '%s' doesn't exist!?" % entry['file'], log)
                filedump = base64.encodestring(open(entry['file']).read())
                addresult = client.core.add_torrent_file(entry['title'], filedump, opts)
                addresult.addCallback(on_success, entry, config).addErrback(on_fail, entry, feed)
                dlist.append(addresult)
                # clean up temp file if download plugin is not configured for this feed
                if not 'download' in feed.config:
                    os.remove(entry['file'])
                    del(entry['file'])

            def on_complete(result):

                def on_disconnect(result):
                    log.debug('Stopping twisted reactor. result: %s' % result)
                    try:
                        reactor.stop()
                    except twisted.internet.error.ReactorNotRunning:
                        pass
                client.disconnect().addCallback(on_disconnect).addErrback(on_disconnect)

            defer.DeferredList(dlist).addCallback(on_complete)
            
        def on_connect_fail(result):
            # clean up temp files
            for entry in feed.accepted:
                os.remove(entry['file'])
                del(entry['file'])
            # TODO: is aborting the feed the best course of action?
            log.info('Connect failed: %s' % result)
            feed.abort()
            reactor.stop()

        d.addCallback(on_connect_success).addErrback(on_connect_fail)
        reactor.run()

register_plugin(OutputDeluge, 'deluge', priorities=dict(output=1))
