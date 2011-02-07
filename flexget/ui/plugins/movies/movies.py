import time
import logging
from flask import render_template, Module
from flask.helpers import url_for
from flexget.plugin import PluginDependencyError, get_plugin_by_name
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
    imdb_queue = db_session.query(ImdbQueue).all()
    tmdb_lookup = get_plugin_by_name('api_tmdb').instance.lookup
    for item in imdb_queue:
        movie = tmdb_lookup(imdb_id=item.imdb_id)
        if not movie:
            log.debug('No themoviedb result for imdb id %s' % item.imdb_id)
            continue

        for poster in movie.posters:
            if poster.size == 'thumb':
                item.thumb = url_for('.userstatic', filename=poster.get_file())
                break
        item.title = movie.name
        item.year = movie.released.year
        item.overview = movie.overview

    context = {'movies': imdb_queue}
    return render_template('movies/movies.html', **context)


if manager.options.experimental:
    register_plugin(movies_module, menu='Movies')
