from loguru import logger
from requests import RequestException

from flexget import plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.utils.template import RenderError

logger = logger.bind(name='botarr_search')


class BotarrSearch:
    """Search XDCC providers via a `Botarr <https://github.com/ddonindia/Botarr>`_ instance.

    Can be used as a standalone input plugin to list results, or as a search plugin
    with the ``discover`` plugin to automatically find new episodes.

    Each produced entry contains the following fields in addition to the standard ones:

    - ``botarr_network`` -- IRC network name
    - ``botarr_channel`` -- IRC channel name
    - ``botarr_bot`` -- XDCC bot name
    - ``botarr_slot`` -- XDCC pack slot number
    - ``botarr_size`` -- file size in bytes
    - ``botarr_size_str`` -- human-readable file size string

    Example (standalone input)::

      botarr_search:
        url: http://localhost:3001
        query: "Breaking Bad"

    Example (with discover)::

      discover:
        what:
          - next_series_episodes:
              from_start: yes
        from:
          - botarr_search:
              url: http://localhost:3001
              query: "{{series_name}} {{series_id}}"
              providers:
                - Nibl
              max_results: 20
    """

    schema = {
        'type': 'object',
        'properties': {
            'url': {'type': 'string', 'format': 'url'},
            'query': {'type': 'string'},
            'providers': {
                'type': 'array',
                'items': {'type': 'string'},
            },
            'max_results': {'type': 'integer', 'minimum': 1, 'default': 20},
        },
        'required': ['url'],
        'additionalProperties': False,
    }

    def _perform_search(self, task, config, query_string):
        """Execute a search against the Botarr API and return a list of entries."""
        base_url = config['url'].rstrip('/')
        search_url = f'{base_url}/api/search'

        params = {'query': query_string}
        if config.get('providers'):
            params['providers'] = ','.join(config['providers'])

        try:
            logger.debug('Querying Botarr search API: {}', params)
            response = task.requests.get(search_url, params=params)
            response.raise_for_status()
        except RequestException as e:
            logger.error('Failed to query Botarr search API: {}', e)
            return []

        data = response.json()
        results = data.get('results', [])

        max_res = config.get('max_results', 20)
        results = results[:max_res]

        entries = []
        for res in results:
            filename = res.get('file_name') or res.get('filename')
            if not filename:
                logger.debug('Skipping result with no filename: {}', res)
                continue

            url_obj = res.get('url', {})
            network = url_obj.get('network', res.get('server', ''))
            channel = url_obj.get('channel', res.get('channel', ''))
            bot = url_obj.get('bot', res.get('bot', ''))
            slot = url_obj.get('slot', res.get('pack_number', ''))

            irc_url = f'irc://{network}/{channel}/{bot}/{slot}'

            entry = Entry(title=filename, url=irc_url)
            entry['botarr_network'] = network
            entry['botarr_channel'] = channel
            entry['botarr_bot'] = bot
            entry['botarr_slot'] = slot
            entry['botarr_size'] = res.get('file_size') or res.get('size')
            entry['botarr_size_str'] = res.get('size_str')
            entry['botarr_gets'] = res.get('downloads')

            entries.append(entry)

        logger.debug('Botarr returned {} results for query `{}`', len(entries), query_string)
        return entries

    def on_task_input(self, task, config):
        """Return entries from a Botarr search query (standalone input mode)."""
        query = config.get('query', '')
        if not query:
            raise plugin.PluginError(
                '`query` is required when botarr_search is used as an input plugin.'
            )
        return self._perform_search(task, config, query)

    def search(self, task, entry, config):
        """Return entries matching the given task entry (search plugin mode, used with discover)."""
        query_template = config.get('query', '{{title}}')
        try:
            query_string = entry.render(query_template)
        except RenderError as e:
            logger.error(
                'Failed to render botarr_search query template `{}`: {}', query_template, e
            )
            return []

        return self._perform_search(task, config, query_string)


@event('plugin.register')
def register_plugin():
    plugin.register(BotarrSearch, 'botarr_search', interfaces=['task', 'search'], api_ver=2)
