import time
import logging
from flask import render_template, Module, request, redirect, flash
from flask.helpers import url_for
from flexget.plugin import PluginDependencyError, get_plugin_by_name
from flexget.ui.webui import register_plugin, app, manager

try:
    from flexget.plugins.filter_imdb_queue import QueueError
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
    imdb_queue = get_plugin_by_name('imdb_queue_manager').instance.queue_get()
    tmdb_lookup = get_plugin_by_name('api_tmdb').instance.lookup
    for item in imdb_queue:
        movie = tmdb_lookup(imdb_id=item.imdb_id)
        if not movie:
            item.overview = "TMDb lookup was not successful, no overview available."
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


@movies_module.route('/add/<what>', methods=['GET', 'POST'])
def add_to_queue(what):
    imdb_id = request.values.get('imdb_id')
    quality = request.values.get('quality', 'ANY')
    force = request.values.get('force', False)
    queue_manager = get_plugin_by_name('imdb_queue_manager').instance
    try:
        title = queue_manager.queue_add(title=what, imdb_id=imdb_id, quality=quality, force=force)['title']
    except QueueError, e:
        flash(e.message, 'error')
    else:
        flash('%s successfully added to queue.' % title, 'success')
    return redirect(url_for('index'))


@movies_module.route('/del/<imdb_id>')
def del_from_queue(imdb_id):
    queue_manager = get_plugin_by_name('imdb_queue_manager').instance
    try:
        title = queue_manager.queue_del(imdb_id)
    except QueueError, e:
        flash(e.message, 'error')
    else:
        flash('%s removed from queue.' % title, 'delete')
    return redirect(url_for('index'))

if manager.options.experimental:
    register_plugin(movies_module, menu='Movies')
