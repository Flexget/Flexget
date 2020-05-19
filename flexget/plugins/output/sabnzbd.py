from urllib.parse import urlencode

from loguru import logger
from requests import RequestException

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='sabnzbd')


class OutputSabnzbd:
    """
    Example::

      sabnzbd:
        apikey: 123456
        url: http://localhost/sabnzbd/api?
        category: movies

    All parameters::

      sabnzbd:
        apikey: ...
        url: ...
        category: ...
        script: ...
        pp: ...
        priority: ...
    """

    schema = {
        'type': 'object',
        'properties': {
            'key': {'type': 'string'},
            'url': {'type': 'string', 'format': 'url'},
            'category': {'type': 'string'},
            'script': {'type': 'string'},
            'pp': {'type': 'string'},
            'priority': {'type': 'integer'},
            'password': {'type': 'string'},
            'username': {'type': 'string'},
        },
        'required': ['key', 'url'],
        'additionalProperties': False,
    }

    def get_params(self, config):
        params = {}
        if 'key' in config:
            params['apikey'] = config['key']
        if 'category' in config:
            params['cat'] = '%s' % config['category']
        if 'script' in config:
            params['script'] = config['script']
        if 'pp' in config:
            params['pp'] = config['pp']
        if 'priority' in config:
            params['priority'] = config['priority']
        if 'username' in config:
            params['ma_username'] = config['username']
        if 'password' in config:
            params['ma_password'] = config['password']
        return params

    def on_task_output(self, task, config):
        for entry in task.accepted:
            if task.options.test:
                logger.info('Would add into sabnzbd: {}', entry['title'])
                continue

            params = self.get_params(config)
            # allow overriding the category
            if 'category' in entry:
                # Dirty hack over the next few lines to strip out non-ascii
                # chars. We're going to urlencode this, which causes
                # serious issues in python2.x if it's not ascii input.
                params['cat'] = ''.join([x for x in entry['category'] if ord(x) < 128])
            params['name'] = ''.join([x for x in entry['url'] if ord(x) < 128])
            # add cleaner nzb name (undocumented api feature)
            params['nzbname'] = ''.join([x for x in entry['title'] if ord(x) < 128])

            # check whether file is local or remote
            if entry['url'].startswith('file://'):
                params['mode'] = 'addlocalfile'
                params['name'] = entry['location']
            else:
                params['mode'] = 'addurl'

            request_url = config['url'] + urlencode(params)
            logger.debug('request_url: {}', request_url)
            try:
                response = task.requests.get(request_url)
            except RequestException as e:
                logger.critical('Failed to use sabnzbd. Requested {}', request_url)
                logger.critical('Result was: {}', e.args[0])
                entry.fail('sabnzbd unreachable')
                if task.options.debug:
                    logger.exception(e)
                continue

            if 'error' in response.text.lower():
                entry.fail(response.text.replace('\n', ''))
            else:
                logger.info('Added `{}` to SABnzbd', entry['title'])


@event('plugin.register')
def register_plugin():
    plugin.register(OutputSabnzbd, 'sabnzbd', api_ver=2)
