from __future__ import unicode_literals, division, absolute_import
import time
import logging

from flask import redirect, render_template, Blueprint, request, flash, url_for
from sqlalchemy.sql.expression import desc, asc

from flexget.plugin import DependencyError
from flexget.ui.webui import register_plugin, db_session, app
from flexget.ui.utils import pretty_date

try:
    from flexget.plugins.filter.series import Series, Episode, Release, forget_series, forget_series_episode
except ImportError:
    raise DependencyError(issued_by='ui.series', missing='series')


series_module = Blueprint('series', __name__)
log = logging.getLogger('ui.series')


# TODO: refactor this filter to some globally usable place (webui.py?)
#       also flexget/plugins/ui/utils.py needs to be removed
#       ... mainly because we have flexget/utils for that :)
#
# Josh  Changing the package layout to use 'flexget.ui.utils' instead
# says  seems to illeviated the need to do this no? I don't think this
#       will be of use for anything but UI related functions.


@app.template_filter('pretty_age')
def pretty_age_filter(value):
    return pretty_date(time.mktime(value.timetuple()))


@series_module.route('/')
def index():
    releases = db_session.query(Release).order_by(desc(Release.id)).limit(10).all()
    for release in releases:
        if release.downloaded == False and len(release.episode.releases) > 1:
            for prev_rel in release.episode.releases:
                if prev_rel.downloaded:
                    release.previous = prev_rel

    context = {'releases': releases}
    return render_template('series/series.html', **context)


@series_module.context_processor
def series_list():
    """Add series list to all pages under series"""
    return {'report': db_session.query(Series).order_by(asc(Series.name)).all()}


@series_module.route('/<name>')
def episodes(name):
    query = db_session.query(Episode).join(Episode.series)
    episodes = query.filter(Series.name == name).order_by(desc(Episode.identifier)).all()
    context = {'episodes': episodes, 'name': name}
    return render_template('series/series.html', **context)


@series_module.route('/mark/downloaded/<int:rel_id>')
def mark_downloaded(rel_id):
    db_session.query(Release).get(rel_id).downloaded = True
    db_session.commit()
    return redirect('/series')


@series_module.route('/mark/not_downloaded/<int:rel_id>')
def mark_not_downloaded(rel_id):
    db_session.query(Release).get(rel_id).downloaded = False
    db_session.commit()
    return redirect('/series')


@series_module.route('/forget/<int:rel_id>', methods=['POST', 'GET'])
def forget_episode(rel_id):
    """
    Executes a --series-forget statement for an episode.
    Redirects back to the series index.
    """
    release = db_session.query(Release).get(rel_id)

    context = {'release': release, 'command': 'series forget "%s" %s' % (
        release.episode.series.name, release.episode.identifier)}

    if request.method == 'POST':
        if request.form.get('really', False):
            try:
                forget_series_episode(release.episode.series.name, release.episode.identifier)
                flash('Forgot %s %s.' % (
                    release.episode.series.name, release.episode.identifier), 'delete')
            except ValueError as e:
                flash(e.message, 'error')

        return redirect(url_for('.index'))

    return render_template('series/forget.html', **context)


register_plugin(series_module, menu='Series')
