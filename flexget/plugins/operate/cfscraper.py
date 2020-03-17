from collections import OrderedDict

from loguru import logger

from flexget import plugin
from flexget.event import event
from flexget.utils.requests import Session

logger = logger.bind(name='cfscraper')


class CFScraper:
    """
    Plugin that enables scraping of cloudflare protected sites.

    Example::
      cfscraper: yes
    """

    schema = {'type': 'boolean'}

    @plugin.priority(253)
    def on_task_start(self, task, config):
        try:
            import cloudscraper
        except ImportError as e:
            logger.debug('Error importing cloudscraper: {}', e)
            raise plugin.DependencyError(
                'cfscraper', 'cloudscraper', 'cloudscraper module required. ImportError: %s' % e
            )

        class CFScrapeWrapper(Session, cloudscraper.CloudScraper):
            """
            This class allows the FlexGet session to inherit from CloudScraper instead of the requests.Session directly.
            """

            def Challenge_Response(self, resp, **kwargs):
                """Make sure limiters are disabled when doing a cloudflare challenge."""
                if not self.is_reCaptcha_Challenge(resp):
                    # If this is a recaptcha challenge, the request gets sent straight to requests, not our subclass,
                    # so it can't have any extra arguments that requests doesn't expect.
                    kwargs['disable_limiters'] = True
                return super().Challenge_Response(resp, **kwargs)

        if config is True:
            task.requests.headers = OrderedDict(
                [
                    ('User-Agent', task.requests.headers['User-Agent']),
                    ('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'),
                    ('Accept-Language', 'en-US,en;q=0.5'),
                    ('Accept-Encoding', 'gzip, deflate'),
                    ('Connection', 'close'),
                    ('Upgrade-Insecure-Requests', '1'),
                ]
            )
            task.requests = CFScrapeWrapper.create_scraper(task.requests, solveDepth=5)


@event('plugin.register')
def register_plugin():
    plugin.register(CFScraper, 'cfscraper', api_ver=2)
