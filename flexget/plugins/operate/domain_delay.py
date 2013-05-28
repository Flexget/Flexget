from __future__ import unicode_literals, division, absolute_import
import logging

from flexget.plugin import register_plugin

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
        for domain, delay in config.iteritems():
            log.debug('Adding minimum interval of %s between requests to %s' % (delay, domain))
            task.requests.set_domain_delay(domain, delay)


register_plugin(DomainDelay, 'domain_delay', api_ver=2)
