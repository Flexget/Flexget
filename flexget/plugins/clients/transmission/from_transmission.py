from flexget import plugin
from flexget.entry import Entry
from flexget.event import event

from flexget.plugins.clients.transmission.client import create_rpc_client
from flexget.plugins.clients.transmission.utils import torrent_info, check_seed_limits, prepare_config, \
    check_requirements


class FromTransmissionPlugin:
    """
    Creates an entry for each item you have loaded in transmission.

    Example::

      from_transmission:
        host: localhost
        port: 9091
        netrc: /home/flexget/.tmnetrc
        username: myusername
        password: mypassword
        path: the download location

    Default values for the config elements::

      from_transmission:
        host: localhost
        port: 9091
        enabled: yes
        onlycomplete: yes
    """
    schema = {
        'type': 'object',
        'properties': {
            'host': {'type': 'string', 'default': 'localhost'},
            'port': {'type': 'integer', 'default': 9091},
            'netrc': {'type': 'string'},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'enabled': {'type': 'boolean', 'default': True},
            'onlycomplete': {'type': 'boolean', 'default': True}
        },
        'additionalProperties': False
    }

    def __init__(self):
        pass

    def on_task_start(self, task, config):
        check_requirements()

    def on_task_input(self, task, config):
        config = prepare_config(config)
        if not config['enabled']:
            return

        client = create_rpc_client(config)
        entries = []

        # Hack/Workaround for http://flexget.com/ticket/2002
        # TODO: Proper fix
        if 'username' in config and 'password' in config:
            client.http_handler.set_authentication(client.url, config['username'], config['password'])

        session = client.get_session()

        for torrent in client.get_torrents():
            downloaded, bigfella = torrent_info(torrent, config)
            seed_ratio_ok, idle_limit_ok = check_seed_limits(torrent, session)
            if self._should_add(config, torrent, downloaded, seed_ratio_ok, idle_limit_ok):
                entries.append(self._build_entry(torrent, bigfella))
        return entries

    @staticmethod
    def _build_entry(torrent, bigfella):
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
        return entry

    @staticmethod
    def _should_add(config, torrent, downloaded, seed_ratio_ok, idle_limit_ok):

        if not config['onlycomplete']:
            return True

        if not downloaded:
            return False

        if torrent.status == 'stopped' and seed_ratio_ok is None and idle_limit_ok is None:
            return True

        if seed_ratio_ok is True or idle_limit_ok is True:
            return True

        return False


@event('plugin.register')
def register_plugin():
    plugin.register(FromTransmissionPlugin, 'from_transmission', api_ver=2, category='input')
