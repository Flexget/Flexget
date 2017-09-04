from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import re
import logging

from flexget import plugin
from flexget.event import event
from flexget.plugins.internal.urlrewriting import UrlRewritingError

log = logging.getLogger('urlrewrite')


class UrlRewrite(object):
    """
    Generic configurable urlrewriter.

    Example::

      urlrewrite:
        demonoid:
          regexp: http://www\.demonoid\.com/files/details/
          format: http://www.demonoid.com/files/download/HTTP/
    """

    resolves = {}

    schema = {
        'type': 'object',
        'additionalProperties': {
            'type': 'object',
            'properties': {
                'regexp': {'type': 'string', 'format': 'regex'},
                'format': {'type': 'string'}
            },
            'required': ['regexp', 'format'],
            'additionalProperties': False
        }
    }

    def on_task_start(self, task, config):
        resolves = self.resolves[task.name] = {}
        for name, rewrite_config in config.items():
            match = re.compile(rewrite_config['regexp'])
            format = rewrite_config['format']
            resolves[name] = {'regexp_compiled': match, 'format': format, 'regexp': rewrite_config['regexp']}
            log.debug('Added rewrite %s' % name)

    def url_rewritable(self, task, entry):
        log.trace('running url_rewritable')
        log.trace(self.resolves)
        for _, config in self.resolves.get(task.name, {}).items():
            regexp = config['regexp_compiled']
            log.trace('testing %s' % config['regexp'])
            if regexp.search(entry['url']):
                return True
        return False

    def url_rewrite(self, task, entry):
        for name, config in self.resolves.get(task.name, {}).items():
            regexp = config['regexp_compiled']
            format = config['format']
            if regexp.search(entry['url']):
                log.debug('Regexp resolving %s with %s' % (entry['url'], name))

                # run the regexp
                entry['url'] = regexp.sub(format, entry['url'])

                if regexp.match(entry['url']):
                    entry.fail('urlrewriting')
                    raise UrlRewritingError('Regexp %s result should NOT continue to match!' % name)
                return


@event('plugin.register')
def register_plugin():
    plugin.register(UrlRewrite, 'urlrewrite', interfaces=['task', 'urlrewriter'], api_ver=2)
