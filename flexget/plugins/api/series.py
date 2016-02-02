from __future__ import unicode_literals, division, absolute_import

import datetime
from math import ceil

from flask import jsonify
from flask import request
from flask_restplus import inputs
from sqlalchemy.orm.exc import NoResultFound

from flexget.api import api, APIResource
from flexget.plugins.filter import series

series_api = api.namespace('series', description='Flexget Series operations')

begin_object = {
    'type': 'object',
    'properties': {
        'episode_id': {'type': 'integer'},
        'episode_identifier': {'type': 'string'}
    }
}

release_object = {
    'type': 'object',
    'properties': {
        'release_id': {'type': 'integer'},
        'release_title': {'type': 'string'},
        'release_downloaded': {'type': 'string'},
        'release_quality': {'type': 'string'},
        'release_proper_count': {'type': 'integer'},
        'release_first_seen': {'type': 'string'},
        'release_episode_id': {'type': 'integer'}
    }
}

release_schema = {
    'type': 'object',
    'properties': {
        'episode_id': {'type': 'integer'},
        'release': release_object
    }
}
release_schema = api.schema('release_schema', release_schema)

release_list_schema = {
    'type': 'object',
    'properties': {
        'releases': {
            'type': 'array',
            'items': release_object
        },
        'number_of_releases': {'type': 'integer'},
        'episode_id': {'type': 'integer'},
        'show_id': {'type': 'integer'}
    }
}
release_list_schema = api.schema('release_list_schema', release_list_schema)

latest_object = {
    'type': 'object',
    'properties': {
        'episode_id': {'type': 'integer'},
        'episode_identifier': {'type': 'string'},
        'episode_age': {'type': 'string'},
        'number_of_episodes_behind': {'type': 'integer'},
        'downloaded_releases': {
            'type': 'array',
            'items': release_object
        }
    }
}

episode_object = {
    'type': 'object',
    'properties': {
        "episode_first_seen": {'type': 'string'},
        "episode_id": {'type': 'string'},
        "episode_identified_by": {'type': 'string'},
        "episode_identifier": {'type': 'string'},
        "episode_premiere_type": {'type': 'string'},
        "episode_number": {'type': 'string'},
        "episode_season": {'type': 'string'},
        "episode_series_id": {'type': 'string'}
    }
}

show_object = {
    'type': 'object',
    'properties': {
        'show_id': {'type': 'integer'},
        'show_name': {'type': 'string'},
        'begin_episode': begin_object,
        'latest_downloaded_episode': latest_object,
    }
}

series_list_schema = {
    'type': 'object',
    'properties': {
        'shows': {
            'type': 'array',
            'items': show_object
        },
        'number_of_shows': {'type': 'integer'},
        'total_number_of_pages': {'type': 'integer'},
        'page_number': {'type': 'integer'}
    }
}
series_list_schema = api.schema('list_series', series_list_schema)

episode_list_schema = {
    'type': 'object',
    'properties': {
        'episodes': {
            'type': 'array',
            'items': episode_object
        },
        'number_of_episodes': {'type': 'integer'},
        'show_id': {'type': 'integer'},
        'show': {'type': 'string'}
    }
}
episode_list_schema = api.schema('episode_list', episode_list_schema)

episode_schema = {
    'type': 'object',
    'properties': {
        'episode': {'type': episode_object},
        'show_id': {'type': 'integer'},
        'show': {'type': 'string'}
    }
}
episode_schema = api.schema('episode_item', episode_schema)

series_begin_input_schema = {
    'type': 'object',
    'properties': {
        'episode_identifier': {'type': 'string'}
    }
}
series_begin_input_schema = api.schema('begin_item', series_begin_input_schema)


def get_release_details(release):
    release_item = {
        'release_id': release.id,
        'release_title': release.title,
        'release_downloaded': release.downloaded,
        'release_quality': release.quality.name,
        'release_proper_count': release.proper_count,
        'release_first_seen': release.first_seen,
        'release_episode_id': release.episode_id,
    }
    return release_item


def get_episode_details(episode):
    episode_item = {
        'episode_id': episode.id,
        'episode_identifier': episode.identifier,
        'episode_season': episode.season,
        'episode_identified_by': episode.identified_by,
        'episode_number': episode.number,
        'episode_series_id': episode.series_id,
        'episode_first_seen': episode.first_seen,
        'episode_premiere_type': episode.is_premiere
    }
    return episode_item


def get_series_details(show):
    latest_ep = series.get_latest_release(show)
    begin_ep = show.begin

    if begin_ep:
        begin_ep_id = begin_ep.id
        begin_ep_identifier = begin_ep.identifier
    else:
        begin_ep_id = begin_ep_identifier = None

    begin = {
        'episode_id': begin_ep_id,
        'episode_identifier': begin_ep_identifier
    }

    if latest_ep:
        latest_ep_id = latest_ep.id
        latest_ep_identifier = latest_ep.identifier
        latest_ep_age = latest_ep.age
        new_eps_after_latest_ep = series.new_eps_after(latest_ep)
        release = get_release_details(
                sorted(latest_ep.downloaded_releases,
                       key=lambda release: release.first_seen if release.downloaded else None, reverse=True)[0])
    else:
        latest_ep_id = latest_ep_identifier = latest_ep_age = new_eps_after_latest_ep = release = None

    latest = {
        'episode_id': latest_ep_id,
        'episode_identifier': latest_ep_identifier,
        'episode_age': latest_ep_age,
        'number_of_episodes_behind': new_eps_after_latest_ep,
        'last_downloaded_release': release
    }

    show_item = {
        'show_id': show.id,
        'show_name': show.name,
        'begin_episode': begin,
        'latest_downloaded_episode': latest
    }
    return show_item


series_list_parser = api.parser()
series_list_parser.add_argument('in_config', choices=('configured', 'unconfigured', 'all'), default='configured',
                                help="Filter list if shows are currently in configuration.")
series_list_parser.add_argument('premieres', type=inputs.boolean, default=False,
                                help="Filter by downloaded premieres only.")
series_list_parser.add_argument('status', choices=('new', 'stale'), help="Filter by status")
series_list_parser.add_argument('days', type=int,
                                help="Filter status by number of days. Default is 7 for new and 365 for stale")
series_list_parser.add_argument('page', type=int, default=1, help='Page number. Default is 1')
series_list_parser.add_argument('max', type=int, default=100, help='Shows per page. Default is 100.')

series_list_parser.add_argument('sort_by', choices=('show_name', 'episodes_behind_latest', 'last_download_date'),
                                default='show_name',
                                help="Sort response by attribute.")
series_list_parser.add_argument('order', choices=('desc', 'asc'), default='desc', help="Sorting order.")


@series_api.route('/')
@api.doc(description='Use this endpoint to retrieve data on Flexget collected series,'
                     ' add new series to DB and reset episode and releases status')
class SeriesListAPI(APIResource):
    @api.response(400, 'Page does not exist')
    @api.response(200, 'Series list retrieved successfully', series_list_schema)
    @api.doc(parser=series_list_parser)
    def get(self, session=None):
        """ List existing shows """
        args = series_list_parser.parse_args()
        page = args['page']
        max_results = args['max']

        sort_by = args['sort_by']
        order = args['order']
        # In case the default 'desc' order was received
        if order == 'desc':
            order = True
        else:
            order = False

        kwargs = {
            'configured': args.get('in_config'),
            'premieres': args.get('premieres'),
            'status': args.get('status'),
            'days': args.get('days'),
            'session': session

        }

        series_list = series.get_series_summary(**kwargs)
        series_list = series_list.order_by(series.Series.name)

        num_of_shows = series_list.count()
        pages = int(ceil(num_of_shows / float(max_results)))

        shows = sorted_show_list = []
        if page > pages and pages != 0:
            return {'error': 'page %s does not exist' % page}, 400

        start = (page - 1) * max_results
        finish = start + max_results
        if finish > num_of_shows:
            finish = num_of_shows

        for show_number in range(start, finish):
            shows.append(get_series_details(series_list[show_number]))

        if sort_by == 'show_name':
            sorted_show_list = sorted(shows, key=lambda show: show['show_name'], reverse=order)
        elif sort_by == 'episodes_behind_latest':
            sorted_show_list = sorted(shows,
                                      key=lambda show: show['latest_downloaded_episode']['number_of_episodes_behind'],
                                      reverse=order)
        elif sort_by == 'last_download_date':
            sorted_show_list = sorted(shows,
                                      key=lambda show: show['latest_downloaded_episode']['last_downloaded_release'][
                                          'release_first_seen'] if show['latest_downloaded_episode'][
                                          'last_downloaded_release'] else datetime.datetime(1970, 1, 1),
                                      reverse=order)

        return jsonify({
            'shows': sorted_show_list,
            'number_of_shows': num_of_shows,
            'page': page,
            'total_number_of_pages': pages
        })


release_object = {
    'type': 'object',
    'properties': {
        'quality': {'type': 'string'},
        'title': {'type': 'string'},
        'proper_count': {'type': 'integer'},
        'downloaded': {'type': 'boolean'}
    }
}

episode_object = {
    'type': 'object',
    'properties': {
        'identifier': {'type': 'string'},
        'identifier_type': {'type': 'string'},
        'download_age': {'type': 'string'},
        'releases': {
            'type': 'array',
            'items': release_object}
    }
}

show_details_schema = {
    'type': 'object',
    'properties': {
        'episodes': {
            'type': 'array',
            'items': episode_object
        },
        'show': show_object
    }
}

shows_schema = {
    'type': 'object',
    'properties': {
        'shows': {
            'type': 'array',
            'items': show_object
        },
        'number_of_shows': {'type': 'integer'}
    }
}

show_details_schema = api.schema('show_details', show_details_schema)
shows_schema = api.schema('list_of_shows', shows_schema)


@series_api.route('/search/<string:name>')
@api.doc(description='Searches for a show in the DB via its name. Returns a list of matching shows.')
class SeriesGetShowsAPI(APIResource):
    @api.response(200, 'Show list retrieved successfully', shows_schema)
    @api.doc(params={'name': 'Name of the show(s) to search'})
    def get(self, name, session):
        """ List of shows matching lookup name """
        name = series.normalize_series_name(name)
        matches = series.shows_by_name(name, session=session)

        shows = []
        for match in matches:
            shows.append(get_series_details(match))

        return jsonify({
            'shows': shows,
            'number_of_shows': len(shows)
        })


@series_api.route('/<int:show_id>')
@api.doc(params={'show_id': 'ID of the show'}, description='Enable operations on a specific show using its ID')
class SeriesShowAPI(APIResource):
    @api.response(404, 'Show ID not found')
    @api.response(200, 'Show information retrieved successfully', show_details_schema)
    def get(self, show_id, session):
        """ Get show details by ID """
        try:
            show = series.show_by_id(show_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Show with ID %s not found' % show_id
                    }, 404

        show = get_series_details(show)

        return jsonify({
            'show': show
        })

    @api.response(200, 'Removed series from DB')
    @api.response(404, 'Show ID not found')
    def delete(self, show_id, session):
        """ Remove series from DB """
        try:
            show = series.show_by_id(show_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Show with ID %s not found' % show_id
                    }, 404

        name = show.name

        try:
            series.forget_series(name)
        except ValueError as e:
            return {'status': 'error',
                    'message': e.args[0]
                    }, 400
        return {'status': 'success',
                'message': 'successfully removed series `%s` from DB' % name
                }, 200

    @api.response(200, 'Episodes for series will be accepted starting with ep_id')
    @api.response(404, 'Show ID not found')
    @api.validate(series_begin_input_schema)
    def put(self, show_id, session):
        """ Set the initial episode of an existing show """
        try:
            show = series.show_by_id(show_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Show with ID %s not found' % show_id
                    }, 404
        data = request.json
        ep_id = data.get('episode_identifier')
        try:
            series.set_series_begin(show, ep_id)
        except ValueError as e:
            return {'status': 'error',
                    'message': e.args[0]
                    }, 400
        return jsonify({'status': 'success',
                        'message': 'Episodes will be accepted starting with `%s`' % ep_id,
                        'show': get_series_details(show)
                        })


@series_api.route('/<name>')
@api.doc(description="Use this endpoint to add a new show to Flexget's DB and set the 1st initial episode via"
                     " its body. 'episode_identifier' should be one of SxxExx, integer or date "
                     "formatted such as 2012-12-12")
class SeriesBeginByNameAPI(APIResource):
    @api.response(200, 'Adding series and setting first accepted episode to ep_id')
    @api.response(500, 'Show already exists')
    @api.validate(series_begin_input_schema)
    def post(self, name, session):
        """ Create a new show and set its first accepted episode """
        normalized_name = series.normalize_series_name(name)
        matches = series.shows_by_exact_name(normalized_name, session=session)
        if matches:
            return {'status': 'error',
                    'message': 'Show `%s` already exist in DB' % name
                    }, 500
        show = series.Series()
        show.name = name
        session.add(show)
        data = request.json
        ep_id = data.get('episode_identifier')
        try:
            series.set_series_begin(show, ep_id)
        except ValueError as e:
            return {'status': 'error',
                    'message': e.args[0]
                    }, 400
        return jsonify({'status': 'success',
                        'message': 'Successfully added series `%s` and set first accepted episode to `%s`' % (
                            show.name, ep_id),
                        'show': get_series_details(show)
                        })


@api.response(404, 'Show ID not found')
@series_api.route('/<int:show_id>/episodes')
@api.doc(params={'show_id': 'ID of the show'}, description='Use this endpoint to get or delete all episodes of a show')
class SeriesEpisodesAPI(APIResource):
    @api.response(200, 'Episodes retrieved successfully for show', episode_list_schema)
    def get(self, show_id, session):
        """ Get episodes by show ID """
        try:
            show = series.show_by_id(show_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Show with ID %s not found' % show_id
                    }, 404
        episodes = [get_episode_details(episode) for episode in show.episodes]

        return jsonify({'show': show.name,
                        'show_id': show_id,
                        'number_of_episodes': len(episodes),
                        'episodes': episodes})

    @api.response(500, 'Error when trying to forget episode')
    @api.response(200, 'Successfully forgotten all episodes from show')
    def delete(self, show_id, session):
        """ Forgets all episodes of a show"""
        try:
            show = series.show_by_id(show_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Show with ID %s not found' % show_id
                    }, 404

        for episode in show.episodes:
            try:
                series.forget_episodes_by_id(show.id, episode.id)
            except ValueError as e:
                return {'status': 'error',
                        'message': e.args[0]
                        }, 500
        return {'status': 'success',
                'message': 'Successfully forgotten all episodes from show %s' % show_id,
                }, 200


@api.response(404, 'Show ID not found')
@api.response(414, 'Episode ID not found')
@api.response(400, 'Episode with ep_ids does not belong to show with show_id')
@series_api.route('/<int:show_id>/episodes/<int:ep_id>')
@api.doc(params={'show_id': 'ID of the show', 'ep_id': 'Episode ID'},
         description='Use this endpoint to get or delete a specific episode for a show')
class SeriesEpisodeAPI(APIResource):
    @api.response(200, 'Episode retrieved successfully for show', episode_schema)
    def get(self, show_id, ep_id, session):
        """ Get episode by show ID and episode ID"""
        try:
            show = series.show_by_id(show_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Show with ID %s not found' % show_id
                    }, 404
        try:
            episode = series.episode_by_id(ep_id, session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Episode with ID %s not found' % ep_id
                    }, 414
        if not series.episode_in_show(show_id, ep_id):
            return {'status': 'error',
                    'message': 'Episode with id %s does not belong to show %s' % (ep_id, show_id)}, 400
        return jsonify({
            'show': show.name,
            'show_id': show_id,
            'episode': get_episode_details(episode)
        })

    @api.response(200, 'Episode successfully forgotten for show', episode_schema)
    def delete(self, show_id, ep_id, session):
        """ Forgets episode by show ID and episode ID """
        try:
            show = series.show_by_id(show_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Show with ID %s not found' % show_id
                    }, 404
        try:
            episode = series.episode_by_id(ep_id, session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Episode with ID %s not found' % ep_id
                    }, 414
        if not series.episode_in_show(show_id, ep_id):
            return {'status': 'error',
                    'message': 'Episode with id %s does not belong to show %s' % (ep_id, show_id)}, 400

        series.forget_episodes_by_id(show_id, ep_id)
        return {'status': 'success',
                'message': 'Episode %s successfully forgotten for show %s' % (ep_id, show_id)
                }


release_list_parser = api.parser()
release_list_parser.add_argument('downloaded', choices=('downloaded', 'not_downloaded', 'all'), default='all',
                                 help='Filter between release status')


@api.response(404, 'Show ID not found')
@api.response(414, 'Episode ID not found')
@api.response(400, 'Episode with ep_ids does not belong to show with show_id')
@series_api.route('/<int:show_id>/episodes/<int:ep_id>/releases')
@api.doc(params={'show_id': 'ID of the show', 'ep_id': 'Episode ID'},
         parser=release_list_parser,
         description='Use this endpoint to get or delete all information about seen releases for a specific episode of'
                     ' a show. Deleting releases will trigger flexget to re-download an episode if a matching release'
                     ' will be seen again for it.')
class SeriesReleasesAPI(APIResource):
    @api.response(200, 'Releases retrieved successfully for episode', release_list_schema)
    def get(self, show_id, ep_id, session):
        """ Get all episodes releases by show ID and episode ID """
        try:
            show = series.show_by_id(show_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Show with ID %s not found' % show_id
                    }, 404
        try:
            episode = series.episode_by_id(ep_id, session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Episode with ID %s not found' % ep_id
                    }, 414
        if not series.episode_in_show(show_id, ep_id):
            return {'status': 'error',
                    'message': 'Episode with id %s does not belong to show %s' % (ep_id, show_id)}, 400
        args = release_list_parser.parse_args()
        downloaded = args['downloaded']
        release_items = []
        for release in episode.releases:
            if (downloaded == 'downloaded' and release.downloaded) or \
                    (downloaded == 'not_downloaded' and not release.downloaded) or \
                            downloaded == 'all':
                release_items.append(get_release_details(release))

        return jsonify({
            'releases': release_items,
            'number_of_releases': len(release_items),
            'episode_id': ep_id,
            'show_id': show_id

        })

    @api.response(200, 'Successfully deleted all releases for episode')
    def delete(self, show_id, ep_id, session):
        """ Deletes all episodes releases by show ID and episode ID """
        try:
            show = series.show_by_id(show_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Show with ID %s not found' % show_id
                    }, 404
        try:
            episode = series.episode_by_id(ep_id, session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Episode with ID %s not found' % ep_id
                    }, 414
        if not series.episode_in_show(show_id, ep_id):
            return {'status': 'error',
                    'message': 'Episode with id %s does not belong to show %s' % (ep_id, show_id)}, 400

        args = release_list_parser.parse_args()
        downloaded = args['downloaded']
        release_items = []
        for release in episode.releases:
            if (downloaded == 'downloaded' and release.downloaded) or \
                    (downloaded == 'not_downloaded' and not release.downloaded) or \
                            downloaded == 'all':
                release_items.append(release)
        number_of_releases = len(release_items)
        for release in release_items:
            series.delete_release_by_id(release.id)
        return {'status': 'success',
                'message': 'Successfully deleted %s releases for episode %s and show %s' % (
                    number_of_releases, ep_id, show_id)}


@api.response(404, 'Show ID not found')
@api.response(414, 'Episode ID not found')
@api.response(424, 'Release ID not found')
@api.response(400, 'Episode with ep_id does not belong to show with show_id')
@api.response(410, 'Release with rel_id does not belong to episode with ep_id')
@series_api.route('/<int:show_id>/episodes/<int:ep_id>/releases/<int:rel_id>/')
@api.doc(params={'show_id': 'ID of the show', 'ep_id': 'Episode ID', 'rel_id': 'Release ID'},
         description='Use this endpoint to get or delete a specific release from an episode of a show. Deleting a '
                     'release will trigger flexget to re-download an episode if a matching release will be seen again '
                     'for it.')
class SeriesReleaseAPI(APIResource):
    @api.response(200, 'Release retrieved successfully for episode')
    def get(self, show_id, ep_id, rel_id, session):
        ''' Get episode release by show ID, episode ID and release ID '''
        try:
            show = series.show_by_id(show_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Show with ID %s not found' % show_id
                    }, 404
        try:
            episode = series.episode_by_id(ep_id, session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Episode with ID %s not found' % ep_id
                    }, 414
        try:
            release = series.release_by_id(rel_id, session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Release with ID %s not found' % rel_id
                    }, 424
        if not series.episode_in_show(show_id, ep_id):
            return {'status': 'error',
                    'message': 'Episode with id %s does not belong to show %s' % (ep_id, show_id)}, 400
        if not series.release_in_episode(ep_id, rel_id):
            return {'status': 'error',
                    'message': 'Release with id %s does not belong to episode %s' % (rel_id, ep_id)}, 410

        return jsonify({
            'show': show.name,
            'show_id': show_id,
            'episode_id': ep_id,
            'release': get_release_details(release)
        })

    @api.response(200, 'Release successfully deleted')
    def delete(self, show_id, ep_id, rel_id, session):
        ''' Delete episode release by show ID, episode ID and release ID '''
        try:
            show = series.show_by_id(show_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Show with ID %s not found' % show_id
                    }, 404
        try:
            episode = series.episode_by_id(ep_id, session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Episode with ID %s not found' % ep_id
                    }, 414
        try:
            release = series.release_by_id(rel_id, session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Release with ID %s not found' % rel_id
                    }, 424
        if not series.episode_in_show(show_id, ep_id):
            return {'status': 'error',
                    'message': 'Episode with id %s does not belong to show %s' % (ep_id, show_id)}, 400
        if not series.release_in_episode(ep_id, rel_id):
            return {'status': 'error',
                    'message': 'Release with id %s does not belong to episode %s' % (rel_id, ep_id)}, 410

        series.delete_release_by_id(rel_id)
        return {'status': 'success',
                'message': 'Successfully deleted release %s for episode %s and show %s' % (rel_id, ep_id, show_id)}
