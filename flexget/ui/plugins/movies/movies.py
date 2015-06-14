from __future__ import unicode_literals, division, absolute_import
import time
import logging
import posixpath
from flask import render_template, Blueprint, request, redirect, flash, send_file
from flask.helpers import url_for
from flexget.plugin import DependencyError, get_plugin_by_name
from flexget.ui.webui import register_plugin, app, manager
from flexget.utils import qualities

try:
    from flexget.plugins.filter.movie_queue import QueueError, queue_get, queue_add, queue_del, queue_edit
except ImportError:
    raise DependencyError(issued_by='ui.movies', missing='movie_queue')


movies_module = Blueprint('movies', __name__)
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
    movie_queue = queue_get()
    tmdb_lookup = get_plugin_by_name('api_tmdb').instance.lookup
    for item in movie_queue:
        try:
            movie = tmdb_lookup(tmdb_id=item.tmdb_id, only_cached=True)
        except LookupError:
            item.overview = ('TMDb lookup was not successful, no overview available.'
                             'Lookup is being retried in the background.')
            log.debug('No themoviedb result for tmdb id %s' % item.tmdb_id)

            # this is probably not needed since non cached movies are retried also
            # in the cover function
            #
            # import thread
            # thread.start_new_thread(tmdb_lookup, (), {'imdb_id': item.imdb_id})
            continue

        # set thumb, but only if already in cache because retrieving is too slow here
        # movies without cached thumb use img tag reading /cover/<imdb_id> which will
        # retrieve the image and thus allows rendering the page immediattely
        for poster in movie.posters:
            if poster.size == 'thumb':
                thumb = poster.get_file(only_cached=True)
                if thumb:
                    item.thumb = url_for('userstatic', filename=posixpath.join(*thumb))
                break

        item.title = movie.name
        item.year = movie.released and movie.released.year
        item.overview = movie.overview

    context = {'movies': movie_queue}
    return render_template('movies/movies.html', **context)


@movies_module.route('/add', methods=['GET', 'POST'])
def add_to_queue():
    what = request.values.get('what')
    imdb_id = request.values.get('imdb_id')
    # TODO: This is a rather limited selection of quality considering the new quality system. Improve it.
    quality = qualities.Requirements(request.values.get('quality', 'ANY'))
    force = request.values.get('force') == 'on'
    try:
        title = queue_add(title=what, imdb_id=imdb_id, quality=quality, force=force)['title']
    except QueueError as e:
        flash(e.message, 'error')
    else:
        flash('%s successfully added to queue.' % title, 'success')
    return redirect(url_for('.index'))


@movies_module.route('/del')
def del_from_queue():
    imdb_id = request.values.get('imdb_id')
    try:
        title = queue_del(imdb_id=imdb_id)
    except QueueError as e:
        flash(e.message, 'error')
    else:
        flash('%s removed from queue.' % title, 'delete')
    return redirect(url_for('.index'))


@movies_module.route('/edit')
def edit_movie_quality():
    imdb_id = request.values.get('imdb_id')
    quality = request.values.get('quality')
    try:
        queue_edit(quality, imdb_id=imdb_id)
    except QueueError as e:
        flash(e.message, 'error')
    else:
        # TODO: Display movie name instead of id
        flash('%s quality changed to %s' % (imdb_id, quality), 'success')
    return redirect(url_for('.index'))


@movies_module.route('/cover/<imdb_id>')
def cover(imdb_id):
    import os

    # TODO: return '' should be replaced with something sane, http error 404 ?

    tmdb_lookup = get_plugin_by_name('api_tmdb').instance.lookup
    try:
        movie = tmdb_lookup(imdb_id=imdb_id)
    except LookupError:
        log.error('No cached data for %s' % imdb_id)
        return ''

    filepath = None
    for poster in movie.posters:
        if poster.size == 'thumb':
            filepath = os.path.join(manager.config_base, 'userstatic', *poster.get_file())
            break

    if filepath is None:
        log.error('No cover for %s' % imdb_id)
        return ''
    elif not os.path.exists(filepath):
        log.error('File %s does not exist' % filepath)
        return ''

    log.debug('sending thumb file %s' % filepath)
    return send_file(filepath, mimetype='image/png')


register_plugin(movies_module, menu='Movies')
