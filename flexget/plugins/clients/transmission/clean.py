import re
from datetime import datetime
from future.moves.urllib.parse import urlparse

from flexget import plugin
from flexget.event import event
from flexget.config_schema import one_or_more
from flexget.utils.tools import parse_timedelta

from flexget.plugins.clients.transmission.client import create_rpc_client
from flexget.plugins.clients.transmission.transmission import log
from flexget.plugins.clients.transmission.utils import torrent_info, check_seed_limits, prepare_config, \
    check_requirements


class PluginTransmissionClean:
    """
    Remove completed torrents from Transmission.

    Examples::

      clean_transmission: yes  # ignore both time and ratio

      clean_transmission:      # uses transmission's internal limits for idle time and seed ratio ( if defined )
        transmission_seed_limits: yes

      clean_transmission:      # matches time only
        finished_for: 2 hours

      clean_transmission:      # matches ratio only
        min_ratio: 0.5

      clean_transmission:      # matches time OR ratio
        finished_for: 2 hours
        min_ratio: 0.5

    Default values for the config elements::

      clean_transmission:
        host: localhost
        port: 9091
        enabled: yes
    """

    schema = {
        'type': 'object',
        'properties': {
            'host': {'type': 'string', 'default': 'localhost'},
            'port': {'type': 'integer', 'default': 9091},
            'netrc': {'type': 'string', 'default': None},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'enabled': {'type': 'boolean', 'default': True},

            'min_ratio': {'type': 'number', 'default': None},
            'finished_for': {'type': 'string', 'format': 'interval', 'default': None},
            'transmission_seed_limits': {'type': 'boolean', 'default': False},
            'delete_files': {'type': 'boolean', 'default': False},
            'tracker': {'type': 'string', 'format': 'regex', 'default': None},
            'preserve_tracker': {'type': 'string', 'format': 'regex', 'default': None},
            'directories': one_or_more({'type': 'string', 'format': 'regex'}),
        },
        'additionalProperties': False
    }

    def __init__(self):
        pass

    def on_task_start(self, task, config):
        check_requirements()

    def on_task_exit(self, task, config):
        config = prepare_config(config)
        if not config['enabled'] or task.options.learn:
            return

        client = create_rpc_client(config)
        nrat = float(config['min_ratio']) if 'min_ratio' in config else None
        nfor = parse_timedelta(config['finished_for']) if 'finished_for' in config else None
        delete_files = bool(config['delete_files']) if 'delete_files' in config else False
        trans_checks = bool(config['transmission_seed_limits']) if 'transmission_seed_limits' in config else False
        tracker_re = re.compile(config['tracker'], re.IGNORECASE) if 'tracker' in config else None
        preserve_tracker_re = re.compile(config['preserve_tracker'],
                                         re.IGNORECASE) if 'preserve_tracker' in config else None
        directories_re = config.get('directories')

        session = client.get_session()

        remove_ids = []
        for torrent in client.get_torrents():
            log.verbose('Torrent "%s": status: "%s" - ratio: %s -  date added: %s - date done: %s' %
                        (torrent.name, torrent.status, torrent.ratio, torrent.date_added, torrent.date_done))
            downloaded, dummy = torrent_info(torrent, config)
            seed_ratio_ok, idle_limit_ok = check_seed_limits(torrent, session)
            tracker_hosts = (urlparse(tracker['announce']).hostname for tracker in torrent.trackers)
            is_clean_all = nrat is None and nfor is None and trans_checks is False
            is_minratio_reached = nrat and (nrat <= torrent.ratio)
            is_transmission_seedlimit_unset = trans_checks and seed_ratio_ok is None and idle_limit_ok is None
            is_transmission_seedlimit_reached = trans_checks and seed_ratio_ok is True
            is_transmission_idlelimit_reached = trans_checks and idle_limit_ok is True
            is_torrent_seed_only = torrent.date_done <= torrent.date_added
            is_torrent_idlelimit_since_added_reached = nfor and (torrent.date_added + nfor) <= datetime.now()
            is_torrent_idlelimit_since_finished_reached = nfor and (torrent.date_done + nfor) <= datetime.now()
            is_tracker_matching = not tracker_re or any(tracker_re.search(host) for host in tracker_hosts)
            is_preserve_tracker_matching = False
            if preserve_tracker_re is not None:
                is_preserve_tracker_matching = any(preserve_tracker_re.search(host) for host in tracker_hosts)
            is_directories_matching = not directories_re or any(
                re.compile(directory, re.IGNORECASE).search(torrent.downloadDir) for directory in directories_re)
            if (downloaded and (is_clean_all or
                is_transmission_seedlimit_unset or
                is_transmission_seedlimit_reached or
                is_transmission_idlelimit_reached or
                is_minratio_reached or
                (is_torrent_seed_only and is_torrent_idlelimit_since_added_reached) or
                (not is_torrent_seed_only and is_torrent_idlelimit_since_finished_reached)) and
                    is_directories_matching and (not is_preserve_tracker_matching and is_tracker_matching)):
                if task.options.test:
                    log.info('Would remove finished torrent `%s` from transmission', torrent.name)
                    continue
                log.info('Removing finished torrent `%s` from transmission', torrent.name)
                remove_ids.append(torrent.id)
        if remove_ids:
            client.remove_torrent(remove_ids, delete_files)


@event('plugin.register')
def register_plugin():
    plugin.register(PluginTransmissionClean, 'clean_transmission', api_ver=2, category='input')
