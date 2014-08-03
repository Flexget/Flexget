from __future__ import unicode_literals, division, absolute_import
import logging
import xml.etree.ElementTree as ElementTree

from requests import RequestException

from flexget import plugin
from flexget.event import event

try:
    from flexget.plugins.api_tvdb import get_mirror, api_key
except ImportError:
    raise plugin.DependencyError(issued_by='thetvdb_submit', missing='api_tvdb',
                                 message='thetvdb_add/remove requires the `api_tvdb` plugin')


class TVDBSubmit(object):
    
    schema = {
        'type': 'object',
        'properties': {
            'account_id': {'type': 'string'}
        },
        'required': ['account_id'],
        'additionalProperties': False
    }
    
    # Defined by subclasses
    remove = None
    log = None
    
    def exists(self, favs, tvdb_id):
        if favs is not None:
            for series in favs.findall('Series'):
                if series.text == tvdb_id:
                    return True
        return False
    
    @plugin.priority(-255)
    def on_task_output(self, task, config):
        mirror = None
        favs = None
        for entry in task.accepted:
            if entry.get('tvdb_id'):
                tvdb_id = str(entry['tvdb_id'])
                ser_info = entry.get('series_name', tvdb_id)
                if favs is not None:
                    isin = self.exists(favs, tvdb_id)
                    if (self.remove and not isin) or (isin and not self.remove):
                        self.log.verbose('Nothing to do for series %s, skipping...' % ser_info)
                        continue
                if not mirror:
                    mirror = get_mirror()
                url = mirror + 'User_Favorites.php?accountid=%s&type=%s&seriesid=%s' % \
                    (config['account_id'], 'remove' if self.remove else 'add', tvdb_id)
                try:
                    page = task.requests.get(url).content
                except RequestException as e:
                    self.log.error('Error submitting series %s to tvdb: %s' % (tvdb_id, e))
                    continue
                if not page:
                    self.log.error('Null response from tvdb, aborting task.')
                    return
                favs = ElementTree.fromstring(page)
                isin = self.exists(favs, tvdb_id)
                if (isin and not self.remove):
                    self.log.verbose('Series %s added to tvdb favorites.' % ser_info)
                elif (self.remove and not isin):
                    self.log.verbose('Series %s removed from tvdb favorites.' % ser_info)
                else:
                    self.log.info("Operation failed for series %s (don't know why)." % ser_info)


class TVDBAdd(TVDBSubmit):
    """Add all accepted shows to your tvdb favorites."""
    remove = False
    log = logging.getLogger('thetvdb_add')


class TVDBRemove(TVDBSubmit):
    """Remove all accepted shows from your tvdb favorites."""
    remove = True
    log = logging.getLogger('thetvdb_remove')


@event('plugin.register')
def register_plugin():
    plugin.register(TVDBAdd, 'thetvdb_add', api_ver=2)
    plugin.register(TVDBRemove, 'thetvdb_remove', api_ver=2)
