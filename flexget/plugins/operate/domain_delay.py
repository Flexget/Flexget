from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.utils.requests import TimedLimiter

log = logging.getLogger('domain_delay')


class DomainDelay(object):
    """
    Sets a minimum interval between requests to specific domains.

    Example::
      domain_delay:
        mysite.com: 5 seconds
    """

    schema = {'type': 'object', 'additionalProperties': {'type': 'string', 'format': 'interval'}}

    def on_task_start(self, task, config):
        for domain, delay in config.items():
            log.debug('Adding minimum interval of %s between requests to %s' % (delay, domain))
            task.requests.add_domain_limiter(TimedLimiter(domain, delay))


@event('plugin.register')
def register_plugin():
    plugin.register(DomainDelay, 'domain_delay', api_ver=2)
