import logging
import time
import os
import base64
import urllib2
from flexget.plugin import *
from httplib import BadStatusLine
try:
    from multiprocessing import Process, Queue
except ImportError:
    Process = object
    Queue = object
from Queue import Empty

log = logging.getLogger('deluge')


class DelugeDrop:

    """ Stores all the info needed to add a torrent to deluge. """

    def __init__(self, name, filedump, path, movedone, label, queuetotop):
        self.name = name
        self.filedump = filedump
        self.path = path
        self.movedone = movedone
        self.label = label
        self.queuetotop = queuetotop
     
        
class ConnectionDrop:

    """ Stores all the info needed to connect to a deluge 1.2 daemon. """
    
    def __init__(self, host, port, user, password):
        self.host = host
        self.port = port
        self.user = user
        self.password = password

        
class ReactorThread(Process):
    
    """ A thread that will run alongside flexget waiting for torrents to add to deluge. (For deluge 1.2 only) """
    
    def __init__(self, fromcore, tocore):
        self.fromcore = fromcore
        self.tocore = tocore
        Process.__init__(self)
        
    def run(self):

        from deluge.ui.client import client
        from twisted.internet import reactor

        def on_connect_success(result):

            def on_success(torrent_id, drop):
                if not torrent_id:
                    log.info("%s is already loaded in deluge, cannot set movedone, label, or queuetotop." % drop.name)
                    self.tocore.put('dropsuccess')
                    return
                log.info("%s successfully added to deluge." % drop.name)
                movedone = drop.movedone
                if movedone:
                    if not os.path.isdir(movedone):
                        log.debug("movedone path %s doesn't exist, creating" % movedone)
                        os.makedirs(movedone)
                    log.debug("%s move on complete set to %s" % (drop.name, movedone))
                    client.core.set_torrent_move_completed(torrent_id, True)
                    client.core.set_torrent_move_completed_path(torrent_id, movedone)
                if drop.label:
                    client.core.enable_plugin('Label')
                    client.label.add(drop.label)
                    client.label.set_torrent(torrent_id, drop.label)
                    log.debug("%s label set to '%s'" % (drop.name, drop.label))
                if drop.queuetotop:
                    log.debug("%s moved to top of queue" % drop.name)
                    client.core.queue_top([torrent_id])
                self.tocore.put('dropsuccess')

            def on_fail(result):
                self.tocore.put('dropfail')

            # add the torrents
            self.tocore.put('connectsuccess')

            def get_input():
                try:
                    item = self.fromcore.get(False)
                except Empty:
                    reactor.callLater(0.1, get_input)
                    return
                if isinstance(item, DelugeDrop):
                    drop = item
                    opts = {}
                    if drop.path:
                        opts['download_location'] = drop.path
                    addresult = client.core.add_torrent_file(drop.name, drop.filedump, opts)
                    addresult.addCallback(on_success, drop).addErrback(on_fail)
                    reactor.callLater(0.1, get_input)
                elif isinstance(item, ConnectionDrop):
                    log.debug('Connection info received. Already connected to deluge daemon, Ignoring.')
                    self.tocore.put('connectsuccess')
                    reactor.callLater(0.1, get_input)
                elif item == 'end':
                
                    def on_disconnect(result):
                        log.debug('Stopping reactor.' % result)
                        reactor.callLater(0.5, reactor.stop)
                    client.disconnect().addCallback(on_disconnect).addErrback(on_disconnect)
            reactor.callLater(0.1, get_input)
            
        def on_connect_fail(result):
            log.info('Connect to deluge daemon failed: %s' % result)
            self.tocore.put('connectfail')
            reactor.callLater(0.1, reactor.stop())
        
        connection = self.fromcore.get()
        if isinstance(connection, ConnectionDrop):
            d = client.connect(
                host=connection.host,
                port=connection.port,
                username=connection.user,
                password=connection.password)
            d.addCallback(on_connect_success).addErrback(on_connect_fail)
            reactor.run()
        elif connection == 'end':
            log.debug('Ending deluge child process.')
        else:
            self.tocore.put('connectfail')
        

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

    def __init__(self):
        self.deluge12 = False
        self.toreactor = Queue()
        self.fromreactor = Queue()

    def on_process_start(self, feed):
        """
            Register the usable set: keywords. Detect what version of deluge
            is loaded, start the reactor process if using the deluge 1.2 api.
        """
        set_plugin = get_plugin_by_name('set')
        set_plugin.instance.register_keys({'path': 'text', 'movedone': 'text', \
            'queuetotop': 'boolean', 'label': 'text'})
        if not self.deluge12:
            try:
                from deluge.ui.client import sclient
            except:
                try:
                    from multiprocessing import Process, Queue
                except:
                    raise PluginError('Python 2.6 required to use deluge 1.2 api', log)
                try:
                    from deluge.ui.client import client
                except:
                    raise PluginError('Deluge module required.', log)
                try:
                    from twisted.internet import reactor
                except:
                    raise PluginError('Twisted module required', log)
                log.info("Using deluge 1.2 api")
                self.deluge12 = True
                log.debug("Starting thread to run twisted reactor")
                self.reactorthread = ReactorThread(self.toreactor, self.fromreactor)
                self.reactorthread.start()
            else:
                log.info("Using deluge 1.1 api")
                self.deluge12 = False
                
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
            for entry in feed.accepted:
                try:
                    if feed.manager.options.test:
                        log.info('Would download: %s' % entry['title'])
                    else:
                        if not feed.manager.unit_test:
                            log.info('Downloading: %s' % entry['title'])
                        # check if entry must have a path (download: yes)
                        download.instance.download(feed, entry)
                except urllib2.HTTPError, e:
                    feed.fail(entry, 'HTTP error')
                    log.error('HTTPError %s' % e.code)
                except urllib2.URLError, e:
                    feed.fail(entry, 'URL Error')
                    log.error('URLError %s' % e.reason)
                except BadStatusLine:
                    feed.fail(entry, 'BadStatusLine')
                    log.error('Failed to reach server. Reason: %s' % e.reason)
                except IOError, e:
                    feed.fail(entry, 'IOError')
                    if hasattr(e, 'reason'):
                        log.error('Failed to reach server. Reason: %s' % e.reason)
                    elif hasattr(e, 'code'):
                        log.error('The server couldn\'t fulfill the request. Error code: %s' % e.code)

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
        opts = {}
        for entry in feed.accepted:
            try:
                before = sclient.get_session_state()
            except Exception, (errno, msg):
                raise PluginError('Could not communicate with deluge core. %s' % msg, log)
            if feed.manager.options.test:
                return
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
        """ 
        This will pass connection info and torrents to the reactorthread
        process, which adds the torrents to deluge using the 1.2 api.
        We then wait for the reactorthread to return the result.
        """
        if not self.reactorthread.is_alive():
            raise PluginError('Delgue daemon is not connected', log)
        connectiondrop = ConnectionDrop(
            config['host'],
            config['port'],
            config['user'],
            config['pass'])
        self.toreactor.put(connectiondrop)
        result = self.fromreactor.get()
        if result == 'connectsuccess':
            pass
        elif result == 'connectfail':
            raise PluginError('Could not connect to deluge daemon.', log)
        if feed.manager.options.test:
            return
        for entry in feed.accepted:
            name = entry['title']
            # see that temp file is present
            if not os.path.exists(entry['file']):
                tmp_path = os.path.join(feed.manager.config_base, 'temp')
                log.debug('entry: %s' % entry)
                log.debug('temp: %s' % ', '.join(os.listdir(tmp_path)))
                feed.fail(entry, "Downloaded temp file '%s' doesn't exist!" % entry['file'])
                continue
            filedump = base64.encodestring(open(entry['file'], 'rb').read())
            path = os.path.expanduser(entry.get('path', config['path']) % entry)
            movedone = os.path.expanduser(entry.get('movedone', config['movedone']) % entry)
            label = entry.get('label', config['label']).lower()
            qtt = entry.get('queuetotop', config['queuetotop'])
            self.toreactor.put(DelugeDrop(name, filedump, path, movedone, label, qtt))
            result = self.fromreactor.get()
            if result == 'dropsuccess':
                pass
            elif result == 'dropfail':
                feed.fail(entry, 'Could not be added to deluge')
            # clean up temp file if download plugin is not configured
            if not 'download' in feed.config:
                os.remove(entry['file'])
                del(entry['file'])
            
    def on_process_end(self, feed):
        """ Sends signal to shutdown reactorthread """
        if self.deluge12:
            self.toreactor.put('end')
            # Make sure both queues are empty, so processes terminate properly.
            try:
                item = self.fromreactor.get(False)
                item = self.toreactor.get(False)
            except Empty:
                pass
            self.reactorthread.terminate()
            self.deluge12 = False

register_plugin(OutputDeluge, 'deluge', priorities=dict(output=1))
