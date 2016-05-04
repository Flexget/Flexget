from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin
from future.moves.urllib.parse import urlencode

import logging

from flexget import plugin
from flexget.event import event
from requests import RequestException

log = logging.getLogger('sabnzbd')


class OutputSabnzbd(object):
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
        params['mode'] = 'addurl'
        return params

    def on_task_output(self, task, config):
        for entry in task.accepted:
            if task.options.test:
                log.info('Would add into sabnzbd: %s' % entry['title'])
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

            request_url = config['url'] + urlencode(params)
            log.debug('request_url: %s' % request_url)
            try:
                response = task.requests.get(request_url)
            except RequestException as e:
                log.critical('Failed to use sabnzbd. Requested %s' % request_url)
                log.critical('Result was: %s' % e.args[0])
                entry.fail('sabnzbd unreachable')
                if task.options.debug:
                    log.exception(e)
                continue

            if 'error' in response.text.lower():
                entry.fail(response.text.replace('\n', ''))
            else:
                log.info('Added `%s` to SABnzbd' % (entry['title']))


@event('plugin.register')
def register_plugin():
    plugin.register(OutputSabnzbd, 'sabnzbd', api_ver=2)
