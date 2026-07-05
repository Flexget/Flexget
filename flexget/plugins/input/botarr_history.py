from loguru import logger
from requests import RequestException

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event

logger = logger.bind(name='botarr_history')


class BotarrHistory:
    """Produce entries from the `Botarr <https://github.com/ddonindia/Botarr>`_ download history.

    Useful for monitoring completed or failed downloads, triggering post-processing
    tasks, or building an audit trail of what Botarr has downloaded.

    Each produced entry contains the following fields:

    - ``botarr_transfer_id`` -- unique Botarr transfer UUID
    - ``botarr_status`` -- transfer status (e.g. ``Completed``, ``Failed``, ``Downloading``)
    - ``botarr_network`` -- IRC network
    - ``botarr_channel`` -- IRC channel
    - ``botarr_bot`` -- XDCC bot name
    - ``botarr_slot`` -- XDCC pack slot number
    - ``botarr_size`` -- file size in bytes
    - ``botarr_created_at`` -- ISO 8601 timestamp when the transfer was created
    - ``botarr_completed_at`` -- ISO 8601 timestamp when the transfer finished
    - ``botarr_error`` -- error message (only present when the transfer failed)

    When ``only_new`` is enabled (the default), the plugin tracks which transfer IDs
    it has already produced and skips them on subsequent runs, so post-processing
    tasks only fire once per download.

    Example::

      botarr_history:
        url: http://localhost:3001

    Full configuration::

      botarr_history:
        url: http://localhost:3001
        status: completed
        limit: 50
        only_new: yes
    """

    schema = {
        'type': 'object',
        'properties': {
            'url': {'type': 'string', 'format': 'url'},
            'status': {
                'type': 'string',
                'enum': ['Completed', 'Failed', 'Downloading', 'all'],
                'default': 'all',
            },
            'limit': {'type': 'integer', 'minimum': 1, 'default': 50},
            'only_new': {'type': 'boolean', 'default': True},
        },
        'required': ['url'],
        'additionalProperties': False,
    }

    def on_task_input(self, task, config):
        """Fetch Botarr history and return one entry per transfer."""
        base_url = config['url'].rstrip('/')
        history_url = f'{base_url}/api/history'

        params = {'limit': config['limit']}

        try:
            logger.debug('Fetching Botarr history from {}', history_url)
            response = task.requests.get(history_url, params=params)
            response.raise_for_status()
        except RequestException as e:
            raise plugin.PluginError(f'Failed to fetch Botarr history: {e}')

        data = response.json()
        items = data.get('items', [])

        logger.debug('Botarr history returned {} items (total: {})', len(items), data.get('total', '?'))

        # Load previously seen transfer IDs for only_new filtering
        only_new = config.get('only_new', True)
        seen_ids = set()
        if only_new:
            seen_ids = set(task.simple_persistence.get('botarr_seen_ids', []))

        entries = []
        new_ids = []
        for item in items:
            status = item.get('status', '')
            if config['status'] != 'all' and status != config['status']:
                continue

            transfer_id = item.get('id')

            if only_new and transfer_id in seen_ids:
                logger.debug('Skipping already-seen transfer: {}', transfer_id)
                continue

            filename = item.get('file_name') or transfer_id
            network = item.get('network', '')
            channel = item.get('channel', '')
            bot = item.get('bot', '')
            slot = item.get('slot', '')

            irc_url = f'irc://{network}/{channel}/{bot}/{slot}'

            entry = Entry(title=filename, url=irc_url)
            entry['botarr_transfer_id'] = transfer_id
            entry['botarr_status'] = status
            entry['botarr_network'] = network
            entry['botarr_channel'] = channel
            entry['botarr_bot'] = bot
            entry['botarr_slot'] = slot
            entry['botarr_size'] = item.get('size')
            entry['botarr_created_at'] = item.get('created_at')
            entry['botarr_completed_at'] = item.get('completed_at')
            if item.get('error'):
                entry['botarr_error'] = item['error']

            entries.append(entry)
            if transfer_id:
                new_ids.append(transfer_id)

        # Persist newly seen IDs (keep last 500 to avoid unbounded growth)
        if only_new and new_ids:
            all_seen = list(seen_ids) + new_ids
            task.simple_persistence['botarr_seen_ids'] = all_seen[-500:]

        logger.verbose('Produced {} entries from Botarr history', len(entries))
        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(BotarrHistory, 'botarr_history', api_ver=2)
