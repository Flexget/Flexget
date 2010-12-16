import time
import logging
from flask import render_template, Module
from flexget.plugin import PluginDependencyError
from flexget.ui.webui import register_plugin, db_session, app, manager

try:
    from flexget.plugins.filter_imdb_queue import ImdbQueue
except ImportError:
    raise PluginDependencyError('Requires imdb plugin', 'imdb_queue')


movies_module = Module(__name__, url_prefix='/movies')
log = logging.getLogger('ui.movies')


# TODO: refactor this filter to some globally usable place (webui.py?)
#       also flexget/plugins/ui/utils.py needs to be removed
#       ... mainly because we have flexget/utils for that :)


@app.template_filter('pretty_age')
def pretty_age_filter(value):
    from flexget.ui.utils import pretty_date
    return pretty_date(time.mktime(value.timetuple()))


@movies_module.route('/')
def index():
    movies = db_session.query(ImdbQueue).all()

    from themoviedb import TMDB
    import yaml
    
    tmdb = TMDB()

    for item in movies:
        movie = yaml.load(tmdb.imdb_results(item.imdb_id))[0]
        
        if not hasattr(movie, 'keys'):
            log.debug('No themoviedb result for imdb id %s' % item.imdb_id)
            continue
            
        log.debug('processing %s' % movie['name'])
        
        for poster in movie['posters']:
            if poster['image']['size'] == 'thumb':
                item.thumb = poster['image']['url']
                break
        item.year = movie['released'].split('-')[0]
        item.overview = movie['overview']

    context = {'movies': movies}
    return render_template('movies/movies.html', **context)


if manager.options.experimental:
    register_plugin(movies_module, menu='Movies')
