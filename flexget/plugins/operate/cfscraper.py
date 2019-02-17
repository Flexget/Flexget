from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.utils.requests import Session

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
            import cfscrape
        except ImportError as e:
            log.debug('Error importing cfscrape: %s' % e)
            raise plugin.DependencyError(
                'cfscraper', 'cfscrape', 'cfscrape module required. ImportError: %s' % e
            )

        class CFScrapeWrapper(Session, cfscrape.CloudflareScraper):
            """
            This class allows the FlexGet session to inherit from CFScraper instead of the requests.Session directly.
            """

        if config is True:
            task.requests = CFScrapeWrapper.create_scraper(task.requests)


@event('plugin.register')
def register_plugin():
    plugin.register(CFScraper, 'cfscraper', api_ver=2)
