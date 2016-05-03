from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from requests import RequestException

from flexget import plugin
from flexget.event import event
from flexget.utils.database import with_session
from flexget.plugins.input.thetvdb_favorites import TVDBUserFavorite
from flexget.plugins.api_tvdb import TVDBRequest


class TVDBBase(object):
    
    schema = {
        'type': 'object',
        'properties': {
            'username': {'type': 'string'},
            'account_id': {'type': 'string'}
        },
        'required': ['username', 'account_id'],
        'additionalProperties': False
    }

    def get_favs(self, username, session):
        favs = session.query(TVDBUserFavorite).filter(TVDBUserFavorite.username == username).first()
        if not favs:
            favs = TVDBUserFavorite(username=username)
            session.add(favs)
        return favs


class TVDBAdd(TVDBBase):
    """Add all accepted shows to your tvdb favorites."""
    remove = False
    log = logging.getLogger('thetvdb_add')

    @plugin.priority(-255)
    @with_session
    def on_task_output(self, task, config, session=None):

        tvdb_favorites = self.get_favs(config['username'], session)

        for entry in task.accepted:
            if entry.get('tvdb_id'):
                tvdb_id = entry['tvdb_id']
                series_name = entry.get('series_name', tvdb_id)

                if tvdb_id in tvdb_favorites.series_ids:
                    self.log.verbose('Already a fav %s (%s), skipping...' % (series_name, tvdb_id))
                    continue

                try:
                    req = TVDBRequest(username=config['username'], account_id=config['account_id'])
                    req.put('/user/favorites/%s' % tvdb_id)
                except RequestException as e:
                    # 409 is thrown if it was already in the favs
                    if e.response.status_code != 409:
                        entry.fail('Error adding %s to tvdb favorites: %s' % (tvdb_id, str(e)))
                        continue

                tvdb_favorites.series_ids.append(tvdb_id)


class TVDBRemove(TVDBBase):
    """Remove all accepted shows from your tvdb favorites."""
    remove = True
    log = logging.getLogger('thetvdb_remove')

    @plugin.priority(-255)
    @with_session
    def on_task_output(self, task, config, session=None):

        tvdb_favorites = self.get_favs(config['username'], session=session)

        for entry in task.accepted:
            if entry.get('tvdb_id'):
                tvdb_id = entry['tvdb_id']
                series_name = entry.get('series_name', tvdb_id)

                if tvdb_id not in tvdb_favorites.series_ids:
                    self.log.verbose('Not a fav %s (%s), skipping...' % (series_name, tvdb_id))
                    continue

                try:
                    req = TVDBRequest(username=config['username'], account_id=config['account_id'])
                    req.delete('/user/favorites/%s' % tvdb_id)
                except RequestException as e:
                    # 409 is thrown if it was not in the favs
                    if e.response.status_code != 409:
                        entry.fail('Error deleting %s from tvdb favorites: %s' % (tvdb_id, str(e)))
                        continue

                tvdb_favorites.series_ids.remove(tvdb_id)


@event('plugin.register')
def register_plugin():
    plugin.register(TVDBAdd, 'thetvdb_add', api_ver=2)
    plugin.register(TVDBRemove, 'thetvdb_remove', api_ver=2)
