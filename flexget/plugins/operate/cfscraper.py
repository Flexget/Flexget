from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.utils.requests import Session
from collections import OrderedDict

log = logging.getLogger('cfscraper')


class CFScraper(object):
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
            log.debug('Error importing cloudscraper: %s' % e)
            raise plugin.DependencyError(
                'cfscraper', 'cloudscraper', 'cloudscraper module required. ImportError: %s' % e
            )

        class CFScrapeWrapper(Session, cloudscraper.CloudScraper):
            """
            This class allows the FlexGet session to inherit from CloudScraper instead of the requests.Session directly.
            """

        if config is True:
            task.requests.headers = (
                OrderedDict(
                    [
                        ('User-Agent', task.requests.headers['User-Agent']),
                        ('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'),
                        ('Accept-Language', 'en-US,en;q=0.5'),
                        ('Accept-Encoding', 'gzip, deflate'),
                        ('Connection',  'close'),
                        ('Upgrade-Insecure-Requests', '1')
                    ]
                )
            )
            task.requests = CFScrapeWrapper.create_scraper(task.requests)


@event('plugin.register')
def register_plugin():
    plugin.register(CFScraper, 'cfscraper', api_ver=2)
