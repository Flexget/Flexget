from .transmission import TransmissionBase
from flexget import plugin, validator
from flexget.entry import Entry
from flexget.event import event


class TransmissionInputPlugin(TransmissionBase):
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

        session = self.client.get_session()

        for torrent in self.client.get_torrents():
            downloaded, bigfella = self.torrent_info(torrent, config)
            seed_ratio_ok, idle_limit_ok = self.check_seed_limits(torrent, session)
            if not config['onlycomplete'] or (downloaded and
                                                  ((
                                                                       torrent.status == 'stopped' and
                                                                       seed_ratio_ok is None and
                                                                   idle_limit_ok is None) or
                                                       (seed_ratio_ok is True or idle_limit_ok is True))):
                entry = Entry(title=torrent.name,
                              url='file://%s' % torrent.torrentFile,
                              torrent_info_hash=torrent.hashString,
                              content_size=torrent.totalSize / (1024 * 1024))
                for attr in ['comment', 'downloadDir', 'isFinished', 'isPrivate']:
                    entry['transmission_' + attr] = getattr(torrent, attr)
                entry['transmission_trackers'] = [t['announce'] for t in torrent.trackers]
                # bigfella? Is this actually the path to the torrent file? see GitHub #1403
                if bigfella:
                    entry['location'] = bigfella
                entries.append(entry)
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(TransmissionInputPlugin, 'from_transmission', api_ver=2, category='input')
