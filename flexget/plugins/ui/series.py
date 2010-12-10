from flexget.webui import register_plugin, db_session
from flask import render_template, Module
from sqlalchemy.sql.expression import desc, asc
from flexget.plugin import PluginDependencyError

try:
    from flexget.plugins.filter_series import Series, Episode
except ImportError:
    raise PluginDependencyError('Requires series plugin', 'series')

series_module = Module(__name__, url_prefix='/series')


@series_module.route('/')
def index():
    context = {'report': db_session.query(Series).order_by(asc(Series.name)).all()}
    return render_template('series.html', **context)


@series_module.route('/<name>')
def episodes(name):

    context = {'report': db_session.query(Series).order_by(asc(Series.name)).all()}

    series = db_session.query(Series).filter(Series.name == name).first()
    context.update({'episodes': series.episodes, 'name': name})
    
    return render_template('series.html', **context)


register_plugin(series_module, menu='Series')
