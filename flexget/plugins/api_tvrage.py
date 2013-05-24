import tvrage.api
import logging
from flexget.utils.database import with_session


log = logging.getLogger('api_tvrage')
cache = {}    # we ll set episode in the cache to speed things up if multiple session ask for same show (now need to persist it ?)

"""
    See https://github.com/ckreutzer/python-tvrage for more details, it's pretty classic.
    A cache could be handy to avoid querying informations but I guess it should be implemented in
    python-tvrage itself.
"""


@with_session
def lookup_series(name=None, session=None):
    if (name in cache):
        return cache[name]
    cache[name] = tvrage.api.Show(name)
    return cache[name]


@with_session
def lookup_season(name=None, seasonnum=None, session=None):
    show = lookup_series(name=name, session=session)
    return show.season(seasonnum)


@with_session
def lookup_episode(name=None, seasonnum=None, episodenum=None, session=None):
    season = lookup_season(name=name, seasonnum=seasonnum, session=session)
    return season.episode(episodenum)
