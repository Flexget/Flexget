import datetime
import time
import logging

from flask import render_template, Module
from sqlalchemy.sql.expression import desc, asc

from flexget.plugin import PluginDependencyError
from flexget.webui import register_plugin, db_session, app


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
    movies = db_session.query(ImdbQueue).all()
    
    try:
        from themoviedb import tmdb
    except ImportError:
        raise Exception("You need to install themoviedb: easy_install https://github.com/joshuajonah/themoviedb/tarball/master")
    
    for item in movies:
        movie = tmdb.imdb(id=item.imdb_id)
        item.overview = movie.getOverview(0)
        item.thumb = movie.getPoster(0, 'thumb')[0]
        item.year = movie.getReleased(0).split('-')[0]
        
    context = {'movies': movies}
    return render_template('movies.html', **context)
    

register_plugin(movies_module, menu='Movies')
