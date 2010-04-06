import logging
import time
import os
import base64
import urllib2
from flexget.plugin import *
from httplib import BadStatusLine

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
        deluge.accept('boolean', key='automanaged')
        deluge.accept('decimal', key='maxupspeed')
        deluge.accept('decimal', key='maxdownspeed')
        deluge.accept('number', key='maxconnections')
        deluge.accept('number', key='maxupslots')
        deluge.accept('decimal', key='ratio')
        deluge.accept('boolean', key='removeatratio')
        deluge.accept('boolean', key='addpaused')
        deluge.accept('boolean', key='compact')
        deluge.accept('text', key='content_filename')
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
        return config

    def __init__(self):
        self.deluge12 = False
        self.reactorRunning = 0
        self.options = {'maxupspeed': 'max_upload_speed', 'maxdownspeed': 'max_download_speed', \
            'maxconnections': 'max_connections', 'maxupslots': 'max_upload_slots', \
            'automanaged': 'auto_managed', 'ratio': 'stop_ratio', 'removeatratio': 'remove_at_ratio', \
            'addpaused': 'add_paused', 'compact': 'compact_allocation'}

    def on_process_start(self, feed):
        """
            Register the usable set: keywords. Detect what version of deluge
            is loaded, start the reactor process if using the deluge 1.2 api.
        """
        set_plugin = get_plugin_by_name('set')
        set_plugin.instance.register_keys({'path': 'text', 'movedone': 'text', \
            'queuetotop': 'boolean', 'label': 'text', 'automanaged': 'boolean', \
            'maxupspeed': 'decimal', 'maxdownspeed': 'decimal', 'maxupslots': 'number', \
            'maxconnections': 'number', 'ratio': 'decimal', 'removeatratio': 'boolean', \
            'addpaused': 'boolean', 'compact': 'boolean', 'content_filename': 'text'})
        if not self.deluge12:
            try:
                log.debug("Testing for deluge 1.1 API")
                from deluge.ui.client import sclient
                log.debug("1.1 API found")
            except:
                log.debug("Testing for deluge 1.2 API")
                try:
                    from deluge.ui.client import client
                except ImportError, e:
                    raise PluginError('Deluge module and it\'s dependencies required. ImportError: %s' % e, log)
                try:
                    from twisted.internet import reactor
                except:
                    raise PluginError('Twisted module required', log)
                log.info("Using deluge 1.2 api")
                self.deluge12 = True
            else:
                log.info("Using deluge 1.1 api")
                self.deluge12 = False
                
    def on_feed_download(self, feed):
        """
            call download plugin to generate the temp files we will load into deluge
            then verify they are valid torrents
        """
        import deluge.ui.common
        config = self.get_config(feed)
        if not config['enabled']:
            return
        #If the download plugin is not enabled, we need to call it to get our temp .torrent files
        if not 'download' in feed.config:
            download = get_plugin_by_name('download')
            download.instance.get_temp_files(feed)

        #Check torrent files are valid
        for entry in feed.accepted:
            if os.path.exists(entry.get('file', '')):
                #Check if downloaded file is a valid torrent file
                try:
                    info = deluge.ui.common.TorrentInfo(entry['file'])
                except Exception, e:
                    feed.fail(entry, 'Invalid torrent file')
                    log.error("Torrent file appears invalid for: %s", entry['title'])
                    #clean up invalid torrent file
                    os.remove(entry['file'])
                    del(entry['file'])

    def on_feed_output(self, feed):
        """Add torrents to deluge at exit."""
        config = self.get_config(feed)
        # don't add when learning
        if feed.manager.options.learn:
            return
        if not feed.accepted or not config['enabled']:
            return
            
        if self.deluge12:
            self.add_to_deluge12(feed, config)
        else:
            self.add_to_deluge11(feed, config)

    def add_to_deluge11(self, feed, config):
        """ Add torrents to deluge using deluge 1.1.x api. """
        try:
            from deluge.ui.client import sclient
        except:
            raise PluginError('Deluge module required', log)

        sclient.set_core_uri()
        for entry in feed.accepted:
            try:
                before = sclient.get_session_state()
            except Exception, (errno, msg):
                raise PluginError('Could not communicate with deluge core. %s' % msg, log)
            if feed.manager.options.test:
                return
            opts = {}
            path = entry.get('path', config['path'])
            if path:
                opts['download_location'] = os.path.expanduser(path % entry)
            for fopt, dopt in self.options.iteritems():
                value = entry.get(fopt, config.get(fopt))
                if value != None:
                    opts[dopt] = value
                    if fopt == 'ratio':
                        opts['stop_at_ratio'] = True
            
            # check that file is downloaded
            if not 'file' in entry:
                feed.fail(entry, 'file missing?')
                continue
                
            # see that temp file is present
            if not os.path.exists(entry['file']):
                tmp_path = os.path.join(feed.manager.config_base, 'temp')
                log.debug('entry: %s' % entry)
                log.debug('temp: %s' % ', '.join(os.listdir(tmp_path)))
                feed.fail(entry, "Downloaded temp file '%s' doesn't exist!?" % entry['file'])
                continue

            sclient.add_torrent_file([entry['file']], [opts])
            log.info("%s torrent added to deluge with options %s" % (entry['title'], opts))
            # clean up temp file if download plugin is not configured for this feed
            if not 'download' in feed.config:
                os.remove(entry['file'])
                del(entry['file'])
                
            movedone = entry.get('movedone', config['movedone'])
            label = entry.get('label', config['label']).lower()
            queuetotop = entry.get('queuetotop', config.get('queuetotop'))

            # Sometimes deluge takes a moment to add the torrent, wait a second.
            time.sleep(2)
            after = sclient.get_session_state()
            for item in after:
                # find torrentid of just added torrent
                if not item in before:
                    # entry['deluge_torrentid'] = item
                    if movedone:
                        if not os.path.isdir(os.path.expanduser(movedone % entry)):
                            log.debug("movedone path %s doesn't exist, creating" % (movedone % entry))
                            os.makedirs(os.path.expanduser(movedone % entry))
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
    
        """ This is the new add to deluge method, using reactor.iterate """
        
        from deluge.ui.client import client
        from twisted.internet import reactor, defer
        from twisted.internet.task import deferLater
        
        def start_reactor():
            #if this is the first this function is being called, we have to call startRunning
            if self.reactorRunning < 2:
                reactor.startRunning(True)
            self.reactorRunning = 1
            while self.reactorRunning == 1:
                reactor.iterate()
            #if there was an error requiring an exception during reactor running, it should be
            #   thrown here so the reactor loop doesn't exit prematurely
            if self.reactorRunning < 0:
                self.reactorRunning = 2
                raise PluginError('Could not connect to deluge daemon', log)
            self.reactorRunning = 2
                
        def pause_reactor(result):
            self.reactorRunning = result

        def on_connect_success(result, feed):
            if not result:
                # TODO: connect failed? do something
                pass
            if feed.manager.options.test:
            
                def on_disconnect(result):
                    log.debug('Done adding torrents to deluge.')
                    reactor.callLater(0.1, pause_reactor, 0)
                    
                client.disconnect().addCallback(on_disconnect)
                return
                
            def on_success(torrent_id, entry, opts, d):
                dlist = []
                if not torrent_id:
                    log.info("%s is already loaded in deluge, cannot set options." % entry['title'])
                    d.callback(None)
                    return
                log.info("%s successfully added to deluge." % entry['title'])
                if opts['movedone']:
                    if not os.path.isdir(opts['movedone']):
                        log.debug("movedone path %s doesn't exist, creating" % opts['movedone'])
                        os.makedirs(opts['movedone'])
                    dlist.append(client.core.set_torrent_move_completed(torrent_id, True))
                    dlist.append(client.core.set_torrent_move_completed_path(torrent_id, opts['movedone']))
                    log.debug("%s move on complete set to %s" % (entry['title'], opts['movedone']))
                if opts['label']:
                    dlist.append(client.label.set_torrent(torrent_id, opts['label']))
                if opts['queuetotop'] != None:
                    if opts['queuetotop']:
                        dlist.append(client.core.queue_top([torrent_id]))
                        log.debug("%s moved to top of queue" % entry['title'])
                    else:
                        dlist.append(client.core.queue_bottom([torrent_id]))
                        log.debug("%s moved to bottom of queue" % entry['title'])
                if opts.get('content_filename'):

                    def on_get_torrent_status(status, d2):
                        for file in status['files']:
                            # Only rename file if it is > 90% of the content
                            if file['size'] > (status['total_size'] * 0.9):
                                filename = opts['content_filename'] + os.path.splitext(file['path'])[1]
                                counter = 1

                                def file_exists():
                                    # Checks the download path as well as the move completed path for existence of the file
                                    if os.path.exists(os.path.join(status['save_path'], filename)):
                                        return True
                                    elif status.get('move_on_completed') and status.get('move_on_completed_path'):
                                        if os.path.exists(os.path.join(status['move_on_completed_path'], filename)):
                                            return True
                                    else:
                                        return False

                                while file_exists():
                                    # Try appending a (#) suffix till a unique filename is found
                                    filename = ''.join([opts['content_filename'], '(', str(counter), ')', os.path.splitext(file['path'])[1]])
                                    counter += 1
                                log.debug("File %s in %s renamed to %s" % (file['path'], entry['title'], filename))
                                client.core.rename_files(torrent_id, [(file['index'], filename)]).addBoth(d2.callback)
                                break
                        else:
                            log.debug("No files in %s are > 90% of content size, no files renamed." % entry['title'])
                            d2.callback(None)

                    # d2 will callback when the renaming is complete
                    d2 = defer.Deferred()
                    status_keys = ['files', 'total_size', 'save_path', 'move_on_completed_path', 'move_on_completed']
                    client.core.get_torrent_status(torrent_id, status_keys).addCallback(on_get_torrent_status, d2)
                    dlist.append(d2)
                # Callback the deferred passed to us when all jobs are complete
                defer.DeferredList(dlist).addBoth(d.callback)

            def on_fail(result, feed, entry):
                log.info("%s was not added to deluge! %s" % (entry['title'], result))
                feed.fail(entry, "Could not be added to deluge")
            
            # dlist is a list of deferreds that must complete before we exit
            dlist = []
            # loop through entries to get a list of labels to add
            labels = []
            if config.get('label'):
                labels.append(config['label'].lower())
            for entry in feed.accepted:
                if entry.get('label') and not entry['label'].lower() in labels:
                    labels.append(entry['label'].lower())
            if labels:
                client.core.enable_plugin('Label')

                def on_get_labels(d_labels, labels, d):
                    for label in labels:
                        if not label in d_labels:
                            client.label.add(label)
                    d.callback(None)

                d = defer.Deferred()
                client.label.get_labels().addCallback(on_get_labels, labels, d)
                dlist.append(d)
            # add the torrents
            for entry in feed.accepted:
                # see that temp file is present
                if not os.path.exists(entry['file']):
                    tmp_path = os.path.join(feed.manager.config_base, 'temp')
                    log.debug('entry: %s' % entry)
                    log.debug('temp: %s' % ', '.join(os.listdir(tmp_path)))
                    feed.fail(entry, "Downloaded temp file '%s' doesn't exist!" % entry['file'])
                    del(entry['file'])
                    continue
                filedump = base64.encodestring(open(entry['file'], 'rb').read())
                path = os.path.expanduser(entry.get('path', config['path']) % entry)
                opts = {}
                if path:
                    opts['download_location'] = path
                for fopt, dopt in self.options.iteritems():
                    value = entry.get(fopt, config.get(fopt))
                    if value != None:
                        opts[dopt] = value
                        if fopt == 'ratio':
                            opts['stop_at_ratio'] = True
                addresult = client.core.add_torrent_file(entry['title'], filedump, opts)
                # clean up temp file if download plugin is not configured for this feed
                if not 'download' in feed.config:
                    os.remove(entry['file'])
                    del(entry['file'])

                # Make a new set of options, that get set after the torrent has been added
                opts = {}
                opts['movedone'] = os.path.expanduser(entry.get('movedone', config['movedone']) % entry)
                opts['label'] = entry.get('label', config['label']).lower()
                opts['queuetotop'] = entry.get('queuetotop', config.get('queuetotop'))
                opts['content_filename'] = entry.get('content_filename')
                #create a deferred here which we will callback after all work in on_success is done
                d = defer.Deferred()
                addresult.addCallbacks(on_success, on_fail, callbackArgs=(entry, opts, d), errbackArgs=(feed, entry))
                dlist.append(d)
                
            def on_complete(result):

                def on_disconnect(result):
                    log.debug('Done adding torrents to deluge. result: %s' % result)
                    reactor.callLater(0.1, pause_reactor, 0)
                    
                def on_disconnect_fail(result):
                    log.debug('Disconnect from deluge daemon failed, result: %s' % result)
                    reactor.callLater(0.1, pause_reactor, 0)
                    
                #deferLater(reactor, 0.1, client.disconnect).addCallbacks(on_disconnect, errback=on_disconnect_fail)
                client.disconnect().addCallbacks(on_disconnect, errback=on_disconnect_fail)

            defer.DeferredList(dlist, consumeErrors=True).addBoth(on_complete)
            
        def on_connect_fail(result, feed):
            log.info('connect failed result: %s' % result)
            # clean up temp file if download plugin is not configured for this feed
            if not 'download' in feed.config:
                for entry in feed.accepted:
                    if os.path.exists(entry.get('file', '')):
                        os.remove(entry['file'])
                        del(entry['file'])
            log.debug('Connect to deluge daemon failed, result: %s' % result)
            reactor.callLater(0.1, pause_reactor, -1)
            
        d = client.connect(
            host=config['host'],
            port=config['port'],
            username=config['user'],
            password=config['pass'])

        #d.addCallbacks(on_connect_success, on_connect_fail, (feed), None, (feed))
        d.addCallback(on_connect_success, feed).addErrback(on_connect_fail, feed)
        start_reactor()
        
    def on_process_end(self, feed):
        if self.deluge12 and self.reactorRunning == 2:
            from twisted.internet import reactor
            reactor.fireSystemEvent('shutdown')
            self.reactorRunning = 0

register_plugin(OutputDeluge, 'deluge', priorities=dict(output=129, process_start=127, download=127))
