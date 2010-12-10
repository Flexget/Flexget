from itertools import groupby

from flask import render_template, Module
from sqlalchemy.sql.expression import desc, asc

from flexget.plugin import PluginDependencyError
from flexget.webui import register_plugin, db_session, app

import datetime
import time
import logging

from utils import pretty_date

try:
    from flexget.plugins.filter_series import Series, Episode, Release
except ImportError:
    raise PluginDependencyError('Requires series plugin', 'series')


series_module = Module(__name__, url_prefix='/series')
log = logging.getLogger('ui.series')


# TODO: refactor this filter to some globally usable place (webui.py?)
#       also flexget/plugins/ui/utils.py needs to be removed
#       ... mainly because we have flexget/utils for that :)


@app.template_filter('pretty_age')
def pretty_age_filter(value):
    return pretty_date(time.mktime(value.timetuple()))


@series_module.route('/')
def index():
    releases = db_session.query(Release).order_by(desc(Release.id)).slice(0, 10)
    context = {'releases': releases}
    return render_template('series.html', **context)


@series_module.context_processor
def series_list():
    """Add series list to all pages under series"""
    return {'report': db_session.query(Series).order_by(asc(Series.name)).all()}


@series_module.route('/<name>')
def episodes(name):
    series = db_session.query(Series).filter(Series.name == name).first()
    context = {'episodes': series.episodes, 'name': name}
    return render_template('series.html', **context)


register_plugin(series_module, menu='Series')
