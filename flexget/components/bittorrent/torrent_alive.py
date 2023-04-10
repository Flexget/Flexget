import binascii
import itertools
import socket
import struct
import threading
from http.client import BadStatusLine
from random import randrange
from urllib.error import URLError
from urllib.parse import quote, urlparse, urlsplit, urlunsplit

from loguru import logger
from requests import RequestException

from flexget import plugin
from flexget.event import event
from flexget.utils import requests
from flexget.utils.bittorrent import bdecode

logger = logger.bind(name='torrent_alive')


class TorrentAliveThread(threading.Thread):
    _counter = itertools.count()

    def __init__(self, tracker, info_hash):
        threading.Thread.__init__(self, name='torrent_alive-%d' % next(self._counter))
        self.tracker = tracker
        self.info_hash = info_hash
        self.tracker_seeds = 0

    def run(self):
        self.tracker_seeds = get_tracker_seeds(self.tracker, self.info_hash)
        logger.debug(
            '{} seeds found from {}',
            self.tracker_seeds,
            get_scrape_url(self.tracker, self.info_hash),
        )


def max_seeds_from_threads(threads):
    """
    Joins the threads and returns the maximum seeds found from any of them.

    :param threads: A list of started `TorrentAliveThread`
    :return: Maximum seeds found from any of the threads
    """
    seeds = 0
    for background in threads:
        logger.debug('Coming up next: {}', background.tracker)
        background.join()
        seeds = max(seeds, background.tracker_seeds)
        logger.debug('Current highest number of seeds found: {}', seeds)
    return seeds


def get_scrape_url(tracker_url, info_hash):
    if 'announce' in tracker_url:
        v = urlsplit(tracker_url)
        result = urlunsplit(
            [v.scheme, v.netloc, v.path.replace('announce', 'scrape'), v.query, v.fragment]
        )
    else:
        logger.debug('`announce` not contained in tracker url, guessing scrape address.')
        result = tracker_url + '/scrape'

    result += '&' if '?' in result else '?'
    result += 'info_hash=%s' % quote(binascii.unhexlify(info_hash))
    return result


def get_udp_seeds(url, info_hash):
    parsed_url = urlparse(url)
    try:
        port = parsed_url.port
    except ValueError:
        logger.error('UDP Port Error, url was {}', url)
        return 0

    logger.debug('Checking for seeds from {}', url)

    connection_id = 0x41727101980  # connection id is always this
    transaction_id = randrange(1, 65535)  # Random Transaction ID creation

    if port is None:
        logger.error('UDP Port Error, port was None')
        return 0

    if port < 0 or port > 65535:
        logger.error('UDP Port Error, port was {}', port)
        return 0

    # Create the socket
    try:
        clisocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        clisocket.settimeout(5.0)
        clisocket.connect((parsed_url.hostname, port))

        # build packet with connection_ID, using 0 value for action, giving our transaction ID for this packet
        packet = struct.pack(b">QLL", connection_id, 0, transaction_id)
        clisocket.send(packet)

        # set 16 bytes ["QLL" = 16 bytes] for the fmq for unpack
        res = clisocket.recv(16)
        # check recieved packet for response
        action, transaction_id, connection_id = struct.unpack(b">LLQ", res)

        # build packet hash out of decoded info_hash
        packet_hash = binascii.unhexlify(info_hash)

        # construct packet for scrape with decoded info_hash setting action byte to 2 for scape
        packet = struct.pack(b">QLL", connection_id, 2, transaction_id) + packet_hash

        clisocket.send(packet)
        # set recieve size of 8 + 12 bytes
        res = clisocket.recv(20)

    except OSError as e:
        logger.warning('Socket Error: {}', e)
        return 0
    # Check for UDP error packet
    (action,) = struct.unpack(b">L", res[:4])
    if action == 3:
        logger.error('There was a UDP Packet Error 3')
        return 0

    # first 8 bytes are followed by seeders, completed and leechers for requested torrent
    seeders, _, _ = struct.unpack(b">LLL", res[8:20])
    logger.debug('get_udp_seeds is returning: {}', seeders)
    clisocket.close()
    return seeders


def get_http_seeds(url, info_hash):
    url = get_scrape_url(url, info_hash)
    if not url:
        logger.debug('if not url is true returning 0')
        return 0
    logger.debug('Checking for seeds from {}', url)

    try:
        data = bdecode(requests.get(url).content).get('files')
    except RequestException as e:
        logger.debug('Error scraping: {}', e)
        return 0
    except SyntaxError as e:
        logger.warning('Error decoding tracker response: {}', e)
        return 0
    except BadStatusLine as e:
        logger.warning('Error BadStatusLine: {}', e)
        return 0
    except OSError as e:
        logger.warning('Server error: {}', e)
        return 0
    if not data:
        logger.debug('No data received from tracker scrape.')
        return 0
    logger.debug('get_http_seeds is returning: {}', list(data.values())[0]['complete'])
    return list(data.values())[0]['complete']


def get_tracker_seeds(url, info_hash):
    if url.startswith('udp'):
        return get_udp_seeds(url, info_hash)
    elif url.startswith('http'):
        return get_http_seeds(url, info_hash)
    else:
        logger.warning('There is a problem with the get_tracker_seeds')
        return 0


class TorrentAlive:
    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {'type': 'integer'},
            {
                'type': 'object',
                'properties': {
                    'min_seeds': {'type': 'integer'},
                    'reject_for': {'type': 'string', 'format': 'interval'},
                },
                'additionalProperties': False,
            },
        ]
    }

    def prepare_config(self, config):
        # Convert config to dict form
        if not isinstance(config, dict):
            config = {'min_seeds': int(config)}
        # Set the defaults
        config.setdefault('min_seeds', 1)
        config.setdefault('reject_for', '1 hour')
        return config

    @plugin.priority(150)
    def on_task_filter(self, task, config):
        if not config:
            return
        config = self.prepare_config(config)
        for entry in task.entries:
            if 'torrent_seeds' in entry and entry['torrent_seeds'] < config['min_seeds']:
                entry.reject(
                    reason='Had < %d required seeds. (%s)'
                    % (config['min_seeds'], entry['torrent_seeds'])
                )

    # Run on output phase so that we let torrent plugin output modified torrent file first
    @plugin.priority(250)
    def on_task_output(self, task, config):
        if not config:
            return
        config = self.prepare_config(config)
        min_seeds = config['min_seeds']

        for entry in task.accepted:
            # If torrent_seeds is filled, we will have already filtered in filter phase
            if entry.get('torrent_seeds'):
                logger.debug(
                    'Not checking trackers for seeds, as torrent_seeds is already filled.'
                )
                continue
            logger.debug('Checking for seeds for {}:', entry['title'])
            torrent = entry.get('torrent')
            if torrent:
                logger.debug('started examining torrent: {}', torrent)
                seeds = 0
                info_hash = torrent.info_hash
                announce_list = torrent.content.get('announce-list')
                if announce_list:
                    # Multitracker torrent
                    threadlist = []
                    for tier in announce_list:
                        for tracker in tier:
                            background = TorrentAliveThread(tracker, info_hash)
                            try:
                                background.start()
                                threadlist.append(background)
                            except threading.ThreadError:
                                # If we can't start a new thread, wait for current ones to complete and continue
                                logger.debug('Reached max threads, finishing current threads.')
                                seeds = max(seeds, max_seeds_from_threads(threadlist))
                                background.start()
                                threadlist = [background]
                            logger.debug(
                                'Started thread to scrape {} with info hash {}', tracker, info_hash
                            )

                    seeds = max(seeds, max_seeds_from_threads(threadlist))
                    logger.debug('Highest number of seeds found: {}', seeds)
                elif torrent.content.get('announce'):
                    # Single tracker
                    tracker = torrent.content['announce']
                    try:
                        seeds = get_tracker_seeds(tracker, info_hash)
                    except URLError as e:
                        logger.debug('Error scraping {}: {}', tracker, e)
                else:
                    logger.warning(
                        'Torrent {} does not seem to have a tracker specified, cannot check for seeders',
                        entry['title'],
                    )
                    return

                # Reject if needed
                if seeds < min_seeds:
                    entry.reject(
                        reason=f'Tracker(s) had < {min_seeds} required seeds. ({seeds})',
                        remember_time=config['reject_for'],
                    )
                    # Maybe there is better match that has enough seeds
                    task.rerun(plugin='torrent_alive', reason='Not enough seeds')
                else:
                    logger.debug('Found {} seeds from trackers', seeds)


@event('plugin.register')
def register_plugin():
    plugin.register(TorrentAlive, 'torrent_alive', api_ver=2)
