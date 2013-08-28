from __future__ import unicode_literals, division, absolute_import
import os
from netrc import netrc, NetrcParseError
import logging
import base64

from flexget.plugin import register_plugin, priority, get_plugin_by_name, PluginError
from flexget import validator
from flexget.entry import Entry
from flexget.utils.template import RenderError
from flexget.utils.pathscrub import pathscrub

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
        if 'netrc' in config:
            netrc_path = os.path.expanduser(config['netrc'])
            try:
                config['username'], _, config['password'] = netrc(netrc_path).authenticators(config['host'])
            except IOError as e:
                log.error('netrc: unable to open: %s' % e.filename)
            except NetrcParseError as e:
                log.error('netrc: %s, file: %s, line: %s' % (e.msg, e.filename, e.lineno))
        return config

    def create_rpc_client(self, config):
        import transmissionrpc
        from transmissionrpc import TransmissionError
        from transmissionrpc import HTTPHandlerError

        user, password = config.get('username'), config.get('password')

        try:
            cli = transmissionrpc.Client(config['host'], config['port'], user, password)
        except TransmissionError as e:
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
    def on_process_start(self, task, config):
        try:
            import transmissionrpc
            from transmissionrpc import TransmissionError
            from transmissionrpc import HTTPHandlerError
        except:
            raise PluginError('Transmissionrpc module version 0.6 or higher required.', log)
        if [int(part) for part in transmissionrpc.__version__.split('.')] < [0, 6]:
            raise PluginError('Transmissionrpc module version 0.6 or higher required, please upgrade', log)

    @save_opener
    def on_task_start(self, task, config):
        config = self.prepare_config(config)
        if config['enabled']:
            if task.manager.options.test:
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

    def on_task_input(self, task, config):
        config = self.prepare_config(config)
        if not config['enabled']:
            return

        if not self.client:
            self.client = self.create_rpc_client(config)
        entries = []

        # Hack/Workaround for http://flexget.com/ticket/2002
        # TODO: Proper fix
        if 'username' in config and 'password' in config:
            self.client.http_handler.set_authentication(self.client.url, config['username'], config['password'])

        for torrent in self.client.info().values():
            torrentCompleted = self._torrent_completed(torrent)
            if not config['onlycomplete'] or torrentCompleted:
                entry = Entry(title=torrent.name,
                              url='file://%s' % torrent.torrentFile,
                              torrent_info_hash=torrent.hashString,
                              content_size=torrent.totalSize/(1024*1024))
                for attr in ['comment', 'downloadDir', 'isFinished', 'isPrivate']:
                        entry['transmission_' + attr] = getattr(torrent, attr)
                entry['transmission_trackers'] = [t['announce'] for t in torrent.trackers]
                entries.append(entry)
        return entries

    def _torrent_completed(self, torrent):
        result = True
        for tf in torrent.files().iteritems():
            result &= (tf[1]['completed'] == tf[1]['size'])
        return result


class PluginTransmission(TransmissionBase):
    """
    Add url from entry url to transmission

    Example::

      transmission:
        host: localhost
        port: 9091
        netrc: /home/flexget/.tmnetrc
        username: myusername
        password: mypassword
        path: the download location
        removewhendone: yes

    Default values for the config elements::

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

    @priority(120)
    def on_task_download(self, task, config):
        """
            Call download plugin to generate the temp files we will load
            into deluge then verify they are valid torrents
        """
        config = self.prepare_config(config)
        if not config['enabled']:
            return
        # If the download plugin is not enabled, we need to call it to get
        # our temp .torrent files
        if not 'download' in task.config:
            download = get_plugin_by_name('download')
            download.instance.get_temp_files(task, handle_magnets=True, fail_html=True)

    @priority(135)
    @save_opener
    def on_task_output(self, task, config):
        from transmissionrpc import TransmissionError
        config = self.prepare_config(config)
        # don't add when learning
        if task.manager.options.learn:
            return
        if not config['enabled']:
            return
        # Do not run if there is nothing to do
        if not task.accepted and not config['removewhendone']:
            return
        if self.client is None:
            self.client = self.create_rpc_client(config)
            if self.client:
                log.debug('Successfully connected to transmission.')
            else:
                raise PluginError("Couldn't connect to transmission.")
        if task.accepted:
            self.add_to_transmission(self.client, task, config)
        if config['removewhendone']:
            try:
                self.remove_finished(self.client)
            except TransmissionError as e:
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

        add = options['add']
        if opt_dic.get('path'):
            try:
                path = os.path.expanduser(entry.render(opt_dic['path']))
                add['download_dir'] = pathscrub(path).encode('utf-8')
            except RenderError as e:
                log.error('Error setting path for %s: %s' % (entry['title'], e))
        if 'addpaused' in opt_dic:
            add['paused'] = opt_dic['addpaused']
        if 'bandwidthpriority' in opt_dic:
            add['bandwidthPriority'] = opt_dic['bandwidthpriority']
        if 'maxconnections' in opt_dic:
            add['peer_limit'] = opt_dic['maxconnections']

        change = options['change']
        if 'honourlimits' in opt_dic and not opt_dic['honourlimits']:
            change['honorsSessionLimits'] = False
        if 'maxupspeed' in opt_dic:
            change['uploadLimit'] = opt_dic['maxupspeed']
            change['uploadLimited'] = True
        if 'maxdownspeed' in opt_dic:
            change['downloadLimit'] = opt_dic['maxdownspeed']
            change['downloadLimited'] = True

        if 'ratio' in opt_dic:
            change['seedRatioLimit'] = opt_dic['ratio']
            if opt_dic['ratio'] == -1:
                # seedRatioMode:
                # 0 follow the global settings
                # 1 override the global settings, seeding until a certain ratio
                # 2 override the global settings, seeding regardless of ratio
                change['seedRatioMode'] = 2
            else:
                change['seedRatioMode'] = 1

        return options

    def add_to_transmission(self, cli, task, config):
        """Adds accepted entries to transmission """
        from transmissionrpc import TransmissionError
        for entry in task.accepted:
            if task.manager.options.test:
                log.info('Would add %s to transmission' % entry['url'])
                continue
            options = self._make_torrent_options_dict(config, entry)

            downloaded = not entry['url'].startswith('magnet:')

            # Check that file is downloaded
            if downloaded and not 'file' in entry:
                entry.fail('file missing?')
                continue

            # Verify the temp file exists
            if downloaded and not os.path.exists(entry['file']):
                tmp_path = os.path.join(task.manager.config_base, 'temp')
                log.debug('entry: %s' % entry)
                log.debug('temp: %s' % ', '.join(os.listdir(tmp_path)))
                entry.fail("Downloaded temp file '%s' doesn't exist!?" % entry['file'])
                continue

            try:
                if downloaded:
                    with open(entry['file'], 'rb') as f:
                        filedump = base64.encodestring(f.read())
                    r = cli.add(filedump, 30, **options['add'])
                else:
                    r = cli.add_uri(entry['url'], timeout=30, **options['add'])
                if r:
                    torrent = r.values()[0]
                log.info('"%s" torrent added to transmission' % (entry['title']))
                if options['change'].keys():
                    for id in r.keys():
                        cli.change(id, 30, **options['change'])
            except TransmissionError as e:
                log.debug('TransmissionError', exc_info=True)
                log.debug('Failed options dict: %s' % options)
                msg = 'TransmissionError: %s' % e.message or 'N/A'
                log.error(msg)
                entry.fail(msg)

    def remove_finished(self, cli):
        # Get a list of active transfers
        transfers = cli.info(arguments=['id', 'hashString', 'name', 'status', 'uploadRatio', 'seedRatioLimit'])
        remove_ids = []
        # Go through the list of active transfers and add finished transfers to remove_ids.
        for transfer in transfers.itervalues():
            log.debug('Transfer "%s": status: "%s" upload ratio: %.2f seed ratio: %.2f' %
                      (transfer.name, transfer.status, transfer.uploadRatio, transfer.seedRatioLimit))
            if transfer.status == 'stopped' and transfer.uploadRatio >= transfer.seedRatioLimit:
                log.info('Removing finished torrent `%s` from transmission' % transfer.name)
                remove_ids.append(transfer.id)
        # Remove finished transfers
        if remove_ids:
            cli.remove(remove_ids)

    def on_task_exit(self, task, config):
        """Make sure all temp files are cleaned up when task exits"""
        # If download plugin is enabled, it will handle cleanup.
        if not 'download' in task.config:
            download = get_plugin_by_name('download')
            download.instance.cleanup_temp_files(task)

    on_task_abort = on_task_exit

register_plugin(PluginTransmission, 'transmission', api_ver=2)
register_plugin(PluginTransmissionInput, 'from_transmission', api_ver=2)
