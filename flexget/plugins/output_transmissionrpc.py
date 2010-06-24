import os
from netrc import netrc, NetrcParseError
import logging
from flexget.plugin import *
from flexget import validator

log = logging.getLogger('transmission')


class PluginTransmissionrpc:
    """
      Add url from entry url to transmission

      Example:

      transmissionrpc:
        host: localhost
        port: 9091
        netrc: /home/flexget/.tmnetrc
        username: myusername
        password: mypassword
        path: the download location
        removewhendone: yes

    Default values for the config elements:

    transmissionrpc:
        host: localhost
        port: 9091
        enabled: yes
        removewhendone: no
    """

    def validator(self):
        """Return config validator"""
        root = validator.factory()
        root.accept('boolean')
        advanced = root.accept('dict')
        advanced.accept('text', key='host')
        advanced.accept('number', key='port')
        # note that password is optional in transmission
        advanced.accept('file', key='netrc', required=False)
        advanced.accept('text', key='username', required=False)
        advanced.accept('text', key='password', required=False)
        advanced.accept('path', key='path', required=False)
        advanced.accept('boolean', key='addpaused', required=False)
        advanced.accept('number', key='maxconnections', required=False)
        advanced.accept('number', key='maxupspeed', required=False)
        advanced.accept('number', key='maxdownspeed', required=False)
        advanced.accept('decimal', key='ratio', required=False)
        advanced.accept('boolean', key='enabled')
        advanced.accept('boolean', key='removewhendone')
        return root

    def get_config(self, feed):
        config = feed.config['transmissionrpc']
        if isinstance(config, bool):
            config = {'enabled': config}
        config.setdefault('enabled', True)
        config.setdefault('host', 'localhost')
        config.setdefault('port', 9091)
        config.setdefault('removewhendone', False)
        return config

    def on_process_start(self, feed):
        """Event handler"""
        try:
            import transmissionrpc
            from transmissionrpc.transmission import TransmissionError
        except:
            raise PluginError('Transmissionrpc module required.', log)
        self.client = None
        set_plugin = get_plugin_by_name('set')
        set_plugin.instance.register_keys({'path': 'text', \
                                           'addpaused': 'boolean', \
                                           'maxconnections': 'number', \
                                           'maxupspeed': 'number',  \
                                           'maxdownspeed': 'number', \
                                           'ratio': 'decimal'})
        config = self.get_config(feed)
        if config['enabled']:
            if feed.manager.options.test:
                log.info('Trying to connect to transmission...')
                self.client = self.create_rpc_client(feed)
                if self.client:
                    log.info('Successfully connected to transmission.')
                else:
                    log.error('It looks like there was a problem connecting to transmission.')
            elif config['removewhendone']:
                self.client = self.create_rpc_client(feed)
                self.remove_finished(self.client)

    @priority(120)
    def on_feed_download(self, feed):
        """
            Call download plugin to generate the temp files we will load
            into deluge then verify they are valid torrents
        """
        config = self.get_config(feed)
        if not config['enabled']:
            return
        # If the download plugin is not enabled, we need to call it to get
        # our temp .torrent files
        if not 'download' in feed.config:
            download = get_plugin_by_name('download')
            download.instance.get_temp_files(feed)

    @priority(135)
    def on_feed_output(self, feed):
        """Event handler"""
        config = self.get_config(feed)
        # don't add when learning
        if feed.manager.options.learn:
            return
        if not config['enabled']:
            return
        # Do not run if there is nothing to do
        if len(feed.accepted) == 0:
            return
        if self.client is None:
            self.client = self.create_rpc_client(feed)
        self.add_to_transmission(self.client, feed)

    def _make_torrent_options_dict(self, feed, entry):

        opt_dic = {}
        config = self.get_config(feed)

        for opt_key in ['path', 'addpaused', 'maxconnections', 'maxupspeed', 'maxdownspeed', 'ratio']:
            if opt_key in entry:
                opt_dic[opt_key] = entry[opt_key]
            elif opt_key in config:
                opt_dic[opt_key] = config[opt_key]

        options = {'add': {}, 'change': {}}

        if 'path' in opt_dic:
            options['add']['download_dir'] = os.path.expanduser(opt_dic['path'])
        if 'addpaused' in opt_dic and opt_dic['addpaused']:
            options['add']['paused'] = True
        if 'maxconnections' in opt_dic:
            options['add']['peer_limit'] = opt_dic['maxconnections']

        if 'maxupspeed' in opt_dic:
            options['change']['uploadLimit'] = opt_dic['maxupspeed']
            options['change']['uploadLimited'] = True
        if 'maxdownspeed' in opt_dic:
            options['change']['downloadLimit'] = opt_dic['maxdownspeed']
            options['change']['downloadLimited'] = True

        if 'ratio' in opt_dic:
            options['change']['seedRatioLimit'] = opt_dic['ratio']
            if opt_dic['ratio'] == -1:
                # seedRatioMode:
                # 0 follow the global settings
                # 1 override the global settings, seeding until a certain ratio
                # 2 override the global settings, seeding regardless of ratio
                options['change']['seedRatioMode'] = 2
            else:
                options['change']['seedRatioMode'] = 1

        return options

    def create_rpc_client(self, feed):
        import transmissionrpc
        from transmissionrpc.transmission import TransmissionError
        from transmissionrpc.httphandler import HTTPHandlerError

        config = self.get_config(feed)
        user, password = None, None

        if 'netrc' in config:
            try:
                user, account, password = netrc(config['netrc']).authenticators(config['host'])
            except IOError, e:
                log.error('netrc: unable to open: %s' % e.filename)
            except NetrcParseError, e:
                log.error('netrc: %s, file: %s, line: %s' % (e.msg, e.filename, e.line))
        else:
            if 'username' in config:
                user = config['username']
            if 'password' in config:
                password = config['password']
        
        try:
            # Hack to prevent failing when the headers plugin is used.
            if 'headers' in feed.config:
                import urllib2
                prev_opener = urllib2._opener
                urllib2.install_opener(None)
                cli = transmissionrpc.Client(config['host'], config['port'], user, password)
                urllib2.install_opener(prev_opener)
            else:
                cli = transmissionrpc.Client(config['host'], config['port'], user, password)
        except TransmissionError, e:
            if isinstance(e.original, HTTPHandlerError):
                if e.original.code == 111:
                    raise PluginError("Cannot connect to transmission. Is it running?")
                elif e.original.code == 401:
                    raise PluginError("Username/password for transmission is incorrect. Cannot connect.")
                elif e.original.code == 110:
                    raise PluginError("Cannot connect to transmission: Connection timed out.")
                else:
                    raise PluginError("Error connecting to transmission: %s" % e.original.message)
            else:
                raise PluginError("Error connecting to transmission: %s" % e.message)
        return cli

    def add_to_transmission(self, cli, feed):
        """Adds accepted entries to transmission """
        from transmissionrpc.transmission import TransmissionError
        for entry in feed.accepted:
            if feed.manager.options.test:
                log.info('Would add %s to transmission' % entry['url'])
                continue
            options = self._make_torrent_options_dict(feed, entry)

            # Check that file is downloaded
            if not 'file' in entry:
                feed.fail(entry, 'file missing?')
                continue

            # Verify the temp file exists
            if not os.path.exists(entry['file']):
                tmp_path = os.path.join(feed.manager.config_base, 'temp')
                log.debug('entry: %s' % entry)
                log.debug('temp: %s' % ', '.join(os.listdir(tmp_path)))
                feed.fail(entry, "Downloaded temp file '%s' doesn't exist!?" % entry['file'])
                continue

            try:
                r = cli.add(None, 30, filename=os.path.abspath(entry['file']), **options['add'])
                log.info("%s torrent added to transmission" % (entry['title']))
                if options['change'].keys():
                    for id in r.keys():
                        cli.change(id, 30, **options['change'])
            except TransmissionError, e:
                log.error(e.message)
                feed.fail(entry)

            # Clean up temp file if download plugin is not configured for
            # this feed.
            if not 'download' in feed.config:
                os.remove(entry['file'])
                del(entry['file'])

    def remove_finished(self, cli):
        # Get a list of active transfers
        transfers = cli.info(arguments=['id', 'hashString', 'name', 'status', 'uploadRatio', 'seedRatioLimit'])
        remove_ids = []
        # Go through the list of active transfers and add finished transfers to remove_ids.
        for tid, transfer in transfers.iteritems():
            log.debug('Transfer "%s": status: "%s" upload ratio: %.2f seed ratio: %.2f' % \
                (transfer.name, transfer.status, transfer.uploadRatio, transfer.seedRatioLimit))
            if transfer.status == 'stopped' and transfer.uploadRatio >= transfer.seedRatioLimit:
                log.info('Remove torrent "%s" from transmission' % (transfer.name))
                remove_ids.append(transfer.id)
        # Remove finished transfers
        if len(remove_ids) > 0:
            cli.remove(remove_ids)

register_plugin(PluginTransmissionrpc, 'transmissionrpc')
