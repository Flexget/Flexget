from itertools import groupby

from flask import render_template, Module
from sqlalchemy.sql.expression import desc, asc

from flexget.plugin import PluginDependencyError
from flexget.webui import register_plugin, db_session, app

from log_viewer import LogEntry


import datetime
import time
import logging

from utils import pretty_date

try:
    from flexget.plugins.filter_imdb_queue import ImdbQueue
    
except ImportError:
    raise PluginDependencyError('Requires imdb plugin', 'movies')


movies_module = Module(__name__, url_prefix='/movies')
log = logging.getLogger('ui.movies')


# TODO: refactor this filter to some globally usable place (webui.py?)
#       also flexget/plugins/ui/utils.py needs to be removed
#       ... mainly because we have flexget/utils for that :)


@app.template_filter('pretty_age')
def pretty_age_filter(value):
    return pretty_date(time.mktime(value.timetuple()))


@movies_module.route('/')
def index():
    movies = db_session.query(LogEntry).filter(LogEntry.logger == 'imdb').order_by(desc(LogEntry.created)).all()
    context = {'movies': movies}
    return render_template('movies.html', **context)

# 
# @movies_module.context_processor
# def series_list():
#     """Add series list to all pages under series"""
#     return {'report': db_session.query(Series).order_by(asc(Series.name)).all()}
# 
# 
# @movies_module.route('/<name>')
# def episodes(name):
#     series = db_session.query(Series).filter(Series.name == name).first()
#     context = {'episodes': series.episodes, 'name': name}
#     return render_template('series.html', **context)


register_plugin(movies_module, menu='Movies')
