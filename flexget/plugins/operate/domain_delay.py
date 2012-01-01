import logging
from flexget import validator
from flexget.plugin import register_plugin

log = logging.getLogger('domain_delay')


class DomainDelay(object):
    """Sets a minimum interval between requests to specific domains."""

    def validator(self):
        root = validator.factory('dict')
        root.accept_valid_keys('interval', key_type='text')
        return root

    def on_feed_start(self, feed, config):
        for domain, delay in config.iteritems():
            log.debug('Adding minimum interval of %s between requests to %s' % (delay, domain))
            feed.requests.set_domain_delay(domain, delay)


register_plugin(DomainDelay, 'domain_delay', api_ver=2)
