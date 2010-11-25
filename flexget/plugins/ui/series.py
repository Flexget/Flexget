from flexget.webui import register_plugin, db_session
from flask import render_template, Module
from flexget.plugins.filter_series import Series, Episode
from sqlalchemy.sql.expression import desc, asc

series_module = Module(__name__, url_prefix='/series')


@series_module.route('/')
def index():
    context = {'report': db_session.query(Series).order_by(asc(Series.name)).all()}
    return render_template('series.html', **context)


@series_module.route('/<name>')
def episodes(name):
    series = db_session.query(Series).filter(Series.name == name).first()
    context = {'episodes': series.episodes, 'name': name}
    return render_template('series_episodes.html', **context)


register_plugin(series_module, menu='Series')
