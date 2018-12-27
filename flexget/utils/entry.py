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


# This function is a little iffy in that it assumes a general structure that is generally dictated by parser plugins
# It's related to https://github.com/Flexget/Flexget/issues/2071
def content_id(entry):
    if entry.get('id'):
        return entry['id']

    # I guess we need to generate one then. Robustness of this section is highly debatable
    entry_id = None
    if is_movie(entry):
        entry_id = entry['movie_name']
        if entry.get('movie_year'):
            entry_id += ' ' + entry['movie_year']
    elif is_show(entry):
        entry_id = entry['series_name']
        if entry.get('series_year'):
            entry_id += ' ' + entry['series_year']
        series_id = None
        if entry.get('series_episode'):
            if entry.get('series_season'):
                series_id = (entry.get('series_season'), entry.get('series_episode'))
            else:
                series_id = (0, entry.get('series_episode'))
        elif entry.get('series_season'):
            series_id = (entry['series_season'], 0)
        elif entry.get('series_date'):
            series_id = entry['series_date']
        entry_id += ' ' + series_id

    if entry_id:
        entry_id = entry_id.strip().lower()
    return entry_id
