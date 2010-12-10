from itertools import groupby

from flask import render_template, Module
from sqlalchemy.sql.expression import desc, asc

from flexget.plugin import PluginDependencyError
from flexget.webui import register_plugin, db_session

import datetime
import time

from utils import pretty_date


try:
    from flexget.plugins.filter_series import Series, Episode, Release
except ImportError:
    raise PluginDependencyError('Requires series plugin', 'series')

series_module = Module(__name__, url_prefix='/series')


@series_module.route('/')
def index():
    
    releases = db_session.query(Release).order_by(desc(Release.id)).slice(0, 10)
    for rel in releases:
        rel.episode.first_seen = pretty_date(time.mktime(rel.episode.first_seen.timetuple()))
        
    context = {'report': db_session.query(Series).order_by(asc(Series.name)).all(), 
                'releases': releases}
    
    return render_template('series.html', **context)


@series_module.route('/<name>')
def episodes(name):

    context = {'report': db_session.query(Series).order_by(asc(Series.name)).all()}

    series = db_session.query(Series).filter(Series.name == name).first()
    context.update({'episodes': series.episodes, 'name': name})
    
    return render_template('series.html', **context)


register_plugin(series_module, menu='Series')
