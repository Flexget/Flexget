from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin


def is_show(entry):
    return entry.get('series_name') or entry.get('tvdb_id', eval_lazy=False)


def is_episode(entry):
    return entry.get('series_season') and entry.get('series_episode')


def is_season(entry):
    return entry.get('series_season') and not is_episode(entry)


def is_movie(entry):
    return bool(entry.get('movie_name'))
