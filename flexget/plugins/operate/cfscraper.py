from __future__ import unicode_literals, division, absolute_import
import logging
 
from flexget import plugin, validator
from flexget.event import event
 
log = logging.getLogger('cfscraper')
 
 
class CFScraper(object):
    """
    Plugin that enables scraping of cloudflare protected sites.

    Example::
      cfscraper: yes
    """
 
    def validator(self):
        return validator.factory('boolean')
 
    @plugin.priority(253)
    def on_task_start(self, task, config):
        try:
            import cfscrape
        except ImportError as e:
            log.debug('Error importing cfscrape: %s' % e)
            raise plugin.DependencyError('cfscraper', 'cfscrape', 'cfscrape module required. ImportError: %s' % e)
        if config is True:
            task.requests = cfscrape.create_scraper(task.requests)
 
 
@event('plugin.register')
def register_plugin():
    plugin.register(CFScraper, 'cfscraper', api_ver=2)
