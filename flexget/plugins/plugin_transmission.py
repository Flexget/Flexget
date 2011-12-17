import os
from netrc import netrc, NetrcParseError
import logging
import base64
from flexget.plugin import register_plugin, priority, get_plugin_by_name, PluginError
from flexget import validator
from flexget.entry import Entry
from flexget.utils.template import RenderError

log = logging.getLogger('transmission')


def save_opener(f):
    """
        Transmissionrpc sets a new default opener for urllib2
        We use this as a decorator to capture and restore it when needed
    """

    def new_f(self, *args, **kwargs):
        import urllib2
        prev_opener = urllib2._opener
        urllib2.install_opener(self.opener)
        try:
            f(self, *args, **kwargs)
            self.opener = urllib2._opener
        finally:
            urllib2.install_opener(prev_opener)
    return new_f


class TransmissionBase(object):

    def __init__(self):
        self.client = None
        self.opener = None

    def _validator(self, advanced):
        """Return config validator"""
        advanced.accept('text', key='host')
        advanced.accept('integer', key='port')
        # note that password is optional in transmission
        advanced.accept('file', key='netrc')
        advanced.accept('text', key='username')
        advanced.accept('text', key='password')
        advanced.accept('boolean', key='enabled')
        return advanced

    def prepare_config(self, config):
        if isinstance(config, bool):
            config = {'enabled': config}
        config.setdefault('enabled', True)
        config.setdefault('host', 'localhost')
        config.setdefault('port', 9091)
        return config

    def create_rpc_client(self, config):
        import transmissionrpc
        from transmissionrpc import TransmissionError
        from transmissionrpc import HTTPHandlerError

        user, password = None, None

        if 'netrc' in config:
            try:
                user, account, password = netrc(config['netrc']).authenticators(config['host'])
            except IOError, e:
                log.error('netrc: unable to open: %s' % e.filename)
            except NetrcParseError, e:
                log.error('netrc: %s, file: %s, line: %s' % (e.msg, e.filename, e.lineno))
        else:
            if 'username' in config:
                user = config['username']
            if 'password' in config:
                password = config['password']

        try:
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

    @save_opener
    def on_process_start(self, feed, config):
        try:
            import transmissionrpc
            from transmissionrpc import TransmissionError
            from transmissionrpc import HTTPHandlerError
        except:
            raise PluginError('Transmissionrpc module version 0.6 or higher required.', log)
        if [int(part) for part in transmissionrpc.__version__.split('.')] < [0, 6]:
            raise PluginError('Transmissionrpc module version 0.6 or higher required, please upgrade', log)
        config = self.prepare_config(config)
        if config['enabled']:
            if feed.manager.options.test:
                log.info('Trying to connect to transmission...')
                self.client = self.create_rpc_client(config)
                if self.client:
                    log.info('Successfully connected to transmission.')
                else:
                    log.error('It looks like there was a problem connecting to transmission.')


class PluginTransmissionInput(TransmissionBase):

    def validator(self):
        """Return config validator"""
        root = validator.factory()
        root.accept('boolean')
        advanced = root.accept('dict')
        self._validator(advanced)
        advanced.accept('boolean', key='onlycomplete')
        return root
    
    def prepare_config(self, config):
        config = TransmissionBase.prepare_config(self, config)
        config.setdefault('onlycomplete', True)
        return config

    def on_feed_input(self, feed, config):
        config = self.prepare_config(config)
        if not config['enabled']:
            return

        if not self.client:
            self.client = self.create_rpc_client(config)
        entries = []
        for torrent in self.client.info().values():
            torrentCompleted = self._torrent_completed(torrent)
            if not config['onlycomplete'] or torrentCompleted:
                entry = Entry(title=torrent.fields['name'],
                              url='file://%s' % torrent.fields['torrentFile'],
                              torrent_info_hash=torrent.fields['hashString'])
                for field in torrent.fields:
                    entry['transmission_' + field] = torrent.fields[field]
                entries.append(entry)
        return entries

    def _torrent_completed(self, torrent):
        result = True
        for tf in torrent.files().iteritems():
            result &= (tf[1]['completed'] != tf[1]['size'])
        return result


class PluginTransmission(TransmissionBase):
    """
      Add url from entry url to transmission

      Example:

      transmission:
        host: localhost
        port: 9091
        netrc: /home/flexget/.tmnetrc
        username: myusername
        password: mypassword
        path: the download location
        removewhendone: yes

    Default values for the config elements:

    transmission:
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
        self._validator(advanced)
        advanced.accept('path', key='path', allow_replacement=True)
        advanced.accept('boolean', key='addpaused')
        advanced.accept('boolean', key='honourlimits')
        advanced.accept('integer', key='bandwidthpriority')
        advanced.accept('integer', key='maxconnections')
        advanced.accept('number', key='maxupspeed')
        advanced.accept('number', key='maxdownspeed')
        advanced.accept('number', key='ratio')
        advanced.accept('boolean', key='removewhendone')
        return root

    def prepare_config(self, config):
        config = TransmissionBase.prepare_config(self, config)
        config.setdefault('removewhendone', False)
        return config

    @save_opener
    def on_process_start(self, feed, config):
        set_plugin = get_plugin_by_name('set')
        set_plugin.instance.register_keys({'path': 'text',
                                           'addpaused': 'boolean',
                                           'honourlimits': 'boolean',
                                           'bandwidthpriority': 'integer',
                                           'maxconnections': 'integer',
                                           'maxupspeed': 'number',
                                           'maxdownspeed': 'number',
                                           'ratio': 'number'})
        super(PluginTransmission, self).on_process_start(feed, config)
        
    @priority(120)
    def on_feed_download(self, feed, config):
        """
            Call download plugin to generate the temp files we will load
            into deluge then verify they are valid torrents
        """
        config = self.prepare_config(config)
        if not config['enabled']:
            return
        # If the download plugin is not enabled, we need to call it to get
        # our temp .torrent files
        if not 'download' in feed.config:
            download = get_plugin_by_name('download')
            download.instance.get_temp_files(feed, handle_magnets=True, fail_html=True)

    @priority(135)
    @save_opener
    def on_feed_output(self, feed, config):
        from transmissionrpc import TransmissionError
        config = self.prepare_config(config)
        # don't add when learning
        if feed.manager.options.learn:
            return
        if not config['enabled']:
            return
        # Do not run if there is nothing to do
        if not feed.accepted and not config['removewhendone']:
            return
        if self.client is None:
            self.client = self.create_rpc_client(config)
            if self.client:
                log.debug('Successfully connected to transmission.')
            else:
                raise PluginError("Couldn't connect to transmission.")
        if feed.accepted:
            self.add_to_transmission(self.client, feed, config)
        if config['removewhendone']:
            try:
                self.remove_finished(self.client)
            except TransmissionError, e:
                log.error('Error while attempting to remove completed torrents from transmission: %s' % e)

    def _make_torrent_options_dict(self, config, entry):

        opt_dic = {}

        for opt_key in ('path', 'addpaused', 'honourlimits', 'bandwidthpriority',
                        'maxconnections', 'maxupspeed', 'maxdownspeed', 'ratio'):
            if opt_key in entry:
                opt_dic[opt_key] = entry[opt_key]
            elif opt_key in config:
                opt_dic[opt_key] = config[opt_key]

        options = {'add': {}, 'change': {}}

        if opt_dic.get('path'):
            try:
                options['add']['download_dir'] = os.path.expanduser(entry.render(opt_dic['path'])).encode('utf-8')
            except RenderError, e:
                log.error('Error setting path for %s: %s' % (entry['title'], e))
        if opt_dic.get('addpaused'):
            options['add']['paused'] = True
        if 'bandwidthpriority' in opt_dic:
            options['add']['bandwidthPriority'] = opt_dic['bandwidthpriority']
        if 'maxconnections' in opt_dic:
            options['add']['peer_limit'] = opt_dic['maxconnections']

        if 'honourlimits' in opt_dic and not opt_dic['honourlimits']:
            options['change']['honorsSessionLimits'] = False
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

    def add_to_transmission(self, cli, feed, config):
        """Adds accepted entries to transmission """
        from transmissionrpc import TransmissionError
        for entry in feed.accepted:
            if feed.manager.options.test:
                log.info('Would add %s to transmission' % entry['url'])
                continue
            options = self._make_torrent_options_dict(config, entry)

            downloaded = not(entry['url'].startswith('magnet:'))

            # Check that file is downloaded
            if downloaded and not 'file' in entry:
                feed.fail(entry, 'file missing?')
                continue

            # Verify the temp file exists
            if downloaded and not os.path.exists(entry['file']):
                tmp_path = os.path.join(feed.manager.config_base, 'temp')
                log.debug('entry: %s' % entry)
                log.debug('temp: %s' % ', '.join(os.listdir(tmp_path)))
                feed.fail(entry, "Downloaded temp file '%s' doesn't exist!?" % entry['file'])
                continue

            try:
                if downloaded:
                    f = open(entry['file'], 'rb')
                    try:
                        filedump = base64.encodestring(f.read())
                    finally:
                        f.close()
                    r = cli.add(filedump, 30, **options['add'])
                else:
                    r = cli.add_uri(entry['url'], timeout=30, **options['add'])
                if r:
                    torrent = r.values()[0]
                    for field in torrent.fields:
                        entry['transmission_' + field] = torrent.fields[field]
                log.info('"%s" torrent added to transmission' % (entry['title']))
                if options['change'].keys():
                    for id in r.keys():
                        cli.change(id, 30, **options['change'])
            except TransmissionError, e:
                log.error(e.message)
                feed.fail(entry)

    def remove_finished(self, cli):
        # Get a list of active transfers
        transfers = cli.info(arguments=['id', 'hashString', 'name', 'status', 'uploadRatio', 'seedRatioLimit'])
        remove_ids = []
        # Go through the list of active transfers and add finished transfers to remove_ids.
        for transfer in transfers.itervalues():
            log.debug('Transfer "%s": status: "%s" upload ratio: %.2f seed ratio: %.2f' % \
                (transfer.name, transfer.status, transfer.uploadRatio, transfer.seedRatioLimit))
            if transfer.status == 'stopped' and transfer.uploadRatio >= transfer.seedRatioLimit:
                log.info('Removing finished torrent `%s` from transmission' % transfer.name)
                remove_ids.append(transfer.id)
        # Remove finished transfers
        if remove_ids:
            cli.remove(remove_ids)

    def on_feed_exit(self, feed, config):
        """Make sure all temp files are cleaned up when feed exits"""
        # If download plugin is enabled, it will handle cleanup.
        if not 'download' in feed.config:
            download = get_plugin_by_name('download')
            download.instance.cleanup_temp_files(feed)

    on_feed_abort = on_feed_exit

register_plugin(PluginTransmission, 'transmission', api_ver=2)
register_plugin(PluginTransmissionInput, 'from_transmission', api_ver=2)
