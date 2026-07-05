import time

from loguru import logger
from requests import RequestException

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='botarr')


class Botarr:
    """Submit XDCC download requests to a `Botarr <https://github.com/ddonindia/Botarr>`_ instance.

    Botarr is an XDCC download manager. This plugin submits the IRC XDCC URL from each
    accepted entry to Botarr's REST API to start the download.

    The entry ``url`` field must be an XDCC IRC URL in the format::

      irc://<network>/<channel>/<bot>/<slot>

    This is automatically provided when used together with the ``botarr_search`` plugin.

    Example::

      botarr:
        url: http://localhost:3001

    Full configuration::

      botarr:
        url: http://localhost:3001
        priority: normal
        poll_for_result: no
        poll_interval: 15
        poll_timeout: 3600
    """

    schema = {
        'type': 'object',
        'properties': {
            'url': {'type': 'string', 'format': 'url'},
            'priority': {
                'type': 'string',
                'enum': ['low', 'normal', 'high', 'urgent'],
                'default': 'normal',
            },
            'poll_for_result': {'type': 'boolean', 'default': False},
            'poll_interval': {'type': 'integer', 'minimum': 5, 'default': 15},
            'poll_timeout': {'type': 'integer', 'minimum': 60, 'default': 3600},
        },
        'required': ['url'],
        'additionalProperties': False,
    }

    def on_task_output(self, task, config):
        """Submit accepted entries to Botarr."""
        if not task.accepted:
            return
        if task.options.learn:
            return

        base_url = config['url'].rstrip('/')
        download_url = f'{base_url}/api/download'

        for entry in task.accepted:
            irc_url = entry.get('url')

            if not irc_url:
                entry.fail('Entry has no url field for Botarr submission.')
                continue

            if not irc_url.startswith('irc://'):
                entry.fail(f"Entry url '{irc_url}' is not an IRC XDCC url (must start with irc://).")
                continue

            payload = {
                'url': irc_url,
                'priority': config['priority'],
                'filename': entry.get('title'),
            }

            if task.options.test:
                logger.info('Would submit to Botarr: {}', irc_url)
                continue

            try:
                logger.debug('Submitting to Botarr: {}', download_url)
                response = task.requests.post(download_url, json=payload)
                response.raise_for_status()
            except RequestException as e:
                if getattr(e, 'response', None) is not None:
                    try:
                        error_msg = e.response.json().get('error', e.response.text)
                    except Exception:
                        error_msg = e.response.text
                    
                    if 'Duplicate release' in error_msg or 'Transfer already exists' in error_msg:
                        logger.info('Botarr already has `{}`: {}', entry['title'], error_msg)
                    else:
                        logger.error('Botarr rejected submission for `{}`: {}', entry['title'], error_msg)
                        entry.fail(f'Botarr rejected submission: {error_msg}')
                else:
                    logger.error('Failed to connect to Botarr at `{}`: {}', base_url, e)
                    entry.fail(f'Failed to connect to Botarr: {e}')
                continue

            result = response.json()
            transfer_id = result.get('transfer_id')

            if not transfer_id:
                logger.warning('Botarr returned success but no transfer_id for `{}`', entry['title'])
                continue

            entry['botarr_transfer_id'] = transfer_id
            logger.info(
                'Successfully submitted `{}` to Botarr (Transfer ID: {})',
                entry['title'],
                transfer_id,
            )

            if config['poll_for_result']:
                self._poll_transfer(task, entry, transfer_id, base_url, config)

    def _poll_transfer(self, task, entry, transfer_id, base_url, config):
        """Poll Botarr until a transfer completes, fails, or the timeout is reached.

        .. note::
            This blocks the FlexGet process for up to ``poll_timeout`` seconds.
            Only enable this if you need synchronous completion feedback.
        """
        poll_url = f'{base_url}/api/transfers/{transfer_id}'
        interval = config['poll_interval']
        timeout = config['poll_timeout']

        logger.info('Polling Botarr for transfer completion (timeout: {}s)', timeout)

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = task.requests.get(poll_url)
                if response.status_code == 200:
                    data = response.json()
                    transfer = data.get('transfer', {})
                    status = transfer.get('status')

                    if status == 'completed':
                        entry['botarr_status'] = status
                        entry['botarr_filename'] = transfer.get('filename')
                        entry['botarr_size'] = transfer.get('size')
                        logger.info('Botarr download completed: {}', transfer.get('filename'))
                        return
                    elif status in ('failed', 'cancelled'):
                        error_msg = transfer.get('error') or status
                        entry['botarr_status'] = status
                        logger.error('Botarr download {}: {}', status, error_msg)
                        entry.fail(f'Botarr download {status}: {error_msg}')
                        return

                    logger.verbose(
                        'Botarr transfer status: {} (progress: {:.1f}%)',
                        status,
                        transfer.get('progress', 0.0),
                    )
                elif response.status_code == 404:
                    logger.warning('Botarr transfer {} not found during polling', transfer_id)
                    entry.fail('Transfer not found in Botarr during polling')
                    return
                else:
                    logger.debug('Botarr poll returned unexpected status {}', response.status_code)
            except RequestException as e:
                logger.debug('Botarr poll request failed: {}', e)

            time.sleep(interval)

        logger.warning('Botarr polling timed out after {}s for transfer {}', timeout, transfer_id)


@event('plugin.register')
def register_plugin():
    plugin.register(Botarr, 'botarr', api_ver=2)
