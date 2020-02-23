from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.utils.requests import TimedLimiter

logger = logger.bind(name='domain_delay')


class DomainDelay:
    """
    Sets a minimum interval between requests to specific domains.

    Example::
      domain_delay:
        mysite.com: 5 seconds
    """

    schema = {'type': 'object', 'additionalProperties': {'type': 'string', 'format': 'interval'}}

    def on_task_start(self, task, config):
        for domain, delay in config.items():
            logger.debug('Adding minimum interval of {} between requests to {}', delay, domain)
            task.requests.add_domain_limiter(TimedLimiter(domain, delay))


@event('plugin.register')
def register_plugin():
    plugin.register(DomainDelay, 'domain_delay', api_ver=2)
