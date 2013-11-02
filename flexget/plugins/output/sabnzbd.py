from __future__ import unicode_literals, division, absolute_import
import logging
import urllib

from flexget import plugin
from flexget.event import event
from flexget.utils.tools import urlopener

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

    def validator(self):
        from flexget import validator
        config = validator.factory('dict')
        config.accept('text', key='key', required=True)
        config.accept('url', key='url', required=True)
        config.accept('text', key='category')
        config.accept('text', key='script')
        config.accept('text', key='pp')
        config.accept('integer', key='priority')
        config.accept('text', key='password')
        config.accept('text', key='username')
        return config

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

            request_url = config['url'] + urllib.urlencode(params)
            log.debug('request_url: %s' % request_url)
            try:
                response = urlopener(request_url, log).read()
            except Exception as e:
                log.critical('Failed to use sabnzbd. Requested %s' % request_url)
                log.critical('Result was: %s' % e)
                entry.fail('sabnzbd unreachable')
                if task.options.debug:
                    log.exception(e)
                continue

            if 'error' in response.lower():
                entry.fail(response.replace('\n', ''))
            else:
                log.info('Added `%s` to SABnzbd' % (entry['title']))


@event('plugin.register')
def register_plugin():
    plugin.register(OutputSabnzbd, 'sabnzbd', api_ver=2)
