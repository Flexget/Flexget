from __future__ import unicode_literals, division, absolute_import

from math import ceil

from flask import request
from flask_restful import inputs
from sqlalchemy.orm.exc import NoResultFound

from flexget.api import api, APIResource, jsonify
from flexget.manager import Session
from flexget.plugins.filter.series import get_latest_release, new_eps_after, get_series_summary, \
    Series, normalize_series_name, shows_by_name, show_by_id, forget_series, \
    set_series_begin, shows_by_exact_name, forget_episodes_by_id, episode_by_id, Episode, delete_release_by_id, Release, \
    release_by_id

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
        "episode_age": {'type': 'string'},
        "episode_first_seen": {'type': 'string'},
        "episode_id": {'type': 'string'},
        "episode_identified_by": {'type': 'string'},
        "episode_identifier": {'type': 'string'},
        "episode_is_premiere": {'type': 'boolean'},
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

series_list_configured_enum_list = ['configured', 'unconfigured', 'all']
series_list_status_enum_list = ['new', 'stale']
series_list_sort_value_enum_list = ['show_name', 'episodes_behind_latest']
series_list_sort_order_enum_list = ['desc', 'asc']


def series_list_configured_enum(value):
    enum = series_list_configured_enum_list
    if value not in enum:
        raise ValueError('Value expected to be in' + ' ,'.join(enum))
    return value


def series_list_status_enum(value):
    enum = series_list_status_enum_list
    if value not in enum:
        raise ValueError('Value expected to be in' + ' ,'.join(enum))
    return value


def series_list_sort_value_enum(value):
    enum = series_list_sort_value_enum_list
    if value not in enum:
        raise ValueError('Value expected to be in' + ' ,'.join(enum))
    return value


def series_list_sort_order_enum(value):
    """ Sort oder enum. Return True for 'desc' and False for 'asc' """
    enum = series_list_sort_order_enum_list
    if value not in enum:
        raise ValueError('Value expected to be in' + ' ,'.join(enum))
    if value == 'desc':
        return True
    return False


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
        'episode_age': episode.age,
        'episode_is_premiere': episode.is_premiere
    }
    return episode_item


def get_series_details(series):
    latest_ep = get_latest_release(series)
    begin_ep = series.begin

    if begin_ep:
        begin_ep_id = begin_ep.id
        begin_ep_identifier = begin_ep.identifier
    else:
        begin_ep_id = begin_ep_identifier = None

    begin = {
        'episode_id': begin_ep_id,
        'episode_identifier': begin_ep_identifier
    }

    downloaded_releases = []

    if latest_ep:
        latest_ep_id = latest_ep.id
        latest_ep_identifier = latest_ep.identifier
        latest_ep_age = latest_ep.age
        new_eps_after_latest_ep = new_eps_after(latest_ep)
        for release in latest_ep.downloaded_releases:
            downloaded_releases.append(get_release_details(release))
    else:
        latest_ep_id = latest_ep_identifier = latest_ep_age = new_eps_after_latest_ep = None

    latest = {
        'episode_id': latest_ep_id,
        'episode_identifier': latest_ep_identifier,
        'episode_age': latest_ep_age,
        'number_of_episodes_behind': new_eps_after_latest_ep,
        'downloaded_releases': downloaded_releases
    }

    show_item = {
        'show_id': series.id,
        'show_name': series.name,
        'begin_episode': begin,
        'latest_downloaded_episode': latest
    }
    return show_item


def episode_in_show(series_id, episode_id):
    with Session() as session:
        episode = session.query(Episode).filter(Episode.id == episode_id).one()
        return episode.series_id == series_id


def release_in_episode(episode_id, release_id):
    with Session() as session:
        release = session.query(Release).filter(Release.id == release_id).one()
        return release.episode_id == episode_id


series_list_parser = api.parser()
series_list_parser.add_argument('in_config', type=series_list_configured_enum, default='configured',
                                help="Filter list if shows are currently in configuration. "
                                     "Filter by {0}. Default is configured.".format(
                                        ' ,'.join(series_list_configured_enum_list)))
series_list_parser.add_argument('premieres', type=inputs.boolean, default=False,
                                help="Filter by downloaded premieres only. Default is False.")
series_list_parser.add_argument('status', type=series_list_status_enum,
                                help="Filter by {0} status".format(' ,'.join(series_list_status_enum_list)))
series_list_parser.add_argument('days', type=int,
                                help="Filter status by number of days. Default is 7 for new and 365 for stale")
series_list_parser.add_argument('page', type=int, default=1, help='Page number. Default is 1')
series_list_parser.add_argument('max', type=int, default=100, help='Shows per page. Default is 100.')
"""
series_list_parser.add_argument('sort_by', type=series_list_sort_value_enum, default='show_name',
                                help="Sort response by {0}. Default is show_name.".format(
                                        ' ,'.join(series_list_sort_value_enum_list)))
series_list_parser.add_argument('order', type=series_list_sort_order_enum, default='desc',
                                help="Sorting order. One of {0}. Default is desc".format(
                                        ' ,'.join(series_list_sort_order_enum_list)))
"""


@series_api.route('/')
class SeriesListAPI(APIResource):
    @api.response(400, 'Page does not exist')
    @api.response(200, 'Series list retrieved successfully', series_list_schema)
    @api.doc(parser=series_list_parser)
    def get(self, session=None):
        """ List existing shows """
        args = series_list_parser.parse_args()
        page = args['page']
        max_results = args['max']
        """
        sort_by = args['sort_by']
        order = args['order']
        # In case the default 'desc' order was received
        if order == 'desc':
            order = True
        """

        kwargs = {
            'configured': args.get('in_config'),
            'premieres': args.get('premieres'),
            'status': args.get('status'),
            'days': args.get('days'),
            'session': session

        }

        series_list = get_series_summary(**kwargs)
        series_list = series_list.order_by(Series.name)

        num_of_shows = series_list.count()
        pages = int(ceil(num_of_shows / float(max_results)))

        shows = []
        if page > pages and pages != 0:
            return {'error': 'page %s does not exist' % page}, 400

        start = (page - 1) * max_results
        finish = start + max_results
        if finish > num_of_shows:
            finish = num_of_shows

        for show_number in range(start, finish):
            shows.append(get_series_details(series_list[show_number]))

        # TODO re-enable sorting
        # sorted_show_list = sorted(shows, key=itemgetter(sort_by), reverse=order)

        return jsonify({
            'shows': shows,
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
class SeriesGetShowsAPI(APIResource):
    @api.response(200, 'Show list retrieved successfully', shows_schema)
    @api.doc(params={'name': 'Name of the show(s) to search'})
    def get(self, name, session):
        """ List of shows matching lookup name """
        name = normalize_series_name(name)
        matches = shows_by_name(name, session=session)

        shows = []
        for match in matches:
            shows.append(get_series_details(match))

        return jsonify({
            'shows': shows,
            'number_of_shows': len(shows)
        })


@series_api.route('/<int:show_id>')
@api.doc(params={'show_id': 'ID of the show'})
class SeriesShowAPI(APIResource):
    @api.response(404, 'Show ID not found')
    @api.response(200, 'Show information retrieved successfully', show_details_schema)
    def get(self, show_id, session):
        """ Get show details by ID """
        try:
            show = show_by_id(show_id, session=session)
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
            show = show_by_id(show_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Show with ID %s not found' % show_id
                    }, 404

        name = show.name

        try:
            forget_series(name)
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
            show = show_by_id(show_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Show with ID %s not found' % show_id
                    }, 404
        data = request.json
        ep_id = data.get('episode_identifier')
        try:
            set_series_begin(show, ep_id)
        except ValueError as e:
            return {'status': 'error',
                    'message': e.args[0]
                    }, 400
        return {'status': 'success',
                'message': 'Episodes for `%s` will be accepted starting with `%s`' % (show.name, ep_id)
                }, 200


@series_api.route('/<name>')
class SeriesBeginByNameAPI(APIResource):
    @api.response(200, 'Adding series and setting first accepted episode to ep_id')
    @api.response(500, 'Show already exists')
    @api.validate(series_begin_input_schema)
    def post(self, name, session):
        """ Create a new show and set its first accepted episode """
        normalized_name = normalize_series_name(name)
        matches = shows_by_exact_name(normalized_name, session=session)
        if matches:
            return {'status': 'error',
                    'message': 'Show `%s` already exist in DB' % name
                    }, 500
        show = Series()
        show.name = name
        session.add(show)
        data = request.json
        ep_id = data.get('episode_identifier')
        try:
            set_series_begin(show, ep_id)
        except ValueError as e:
            return {'status': 'error',
                    'message': e.args[0]
                    }, 400
        return {'status': 'success',
                'message': 'Successfully added series `%s` and set first accepted episode to `%s`' % (
                    show.name, ep_id)
                }, 200


@api.response(404, 'Show ID not found')
@series_api.route('/<int:show_id>/episodes')
@api.doc(params={'show_id': 'ID of the show'})
class SeriesEpisodesAPI(APIResource):
    @api.response(200, 'Episodes retrieved successfully for show', episode_list_schema)
    def get(self, show_id, session):
        """ Get episodes by show ID """
        try:
            show = show_by_id(show_id, session=session)
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
            show = show_by_id(show_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Show with ID %s not found' % show_id
                    }, 404

        for episode in show.episodes:
            try:
                forget_episodes_by_id(show.id, episode.id)
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
@api.doc(params={'show_id': 'ID of the show', 'ep_id': 'Episode ID'})
class SeriesEpisodeAPI(APIResource):
    @api.response(200, 'Episode retrieved successfully for show', episode_schema)
    def get(self, show_id, ep_id, session):
        """ Get episode by show ID and episode ID"""
        try:
            show = show_by_id(show_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Show with ID %s not found' % show_id
                    }, 404
        try:
            episode = episode_by_id(ep_id, session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Episode with ID %s not found' % ep_id
                    }, 414
        if not episode_in_show(show_id, ep_id):
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
            show = show_by_id(show_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Show with ID %s not found' % show_id
                    }, 404
        try:
            episode = episode_by_id(ep_id, session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Episode with ID %s not found' % ep_id
                    }, 414
        if not episode_in_show(show_id, ep_id):
            return {'status': 'error',
                    'message': 'Episode with id %s does not belong to show %s' % (ep_id, show_id)}, 400

        forget_episodes_by_id(show_id, ep_id)
        return {'status': 'success',
                'message': 'Episode %s successfully forgotten for show %s' % (ep_id, show_id)
                }


release_downloaded_enum_list = ['downloaded', 'not_downloaded', 'all']


def release_downloaded_enum(value):
    enum = release_downloaded_enum_list
    if value not in enum:
        raise ValueError('Value expected to be in' + ' ,'.join(enum))
    return value


release_list_parser = api.parser()
release_list_parser.add_argument('downloaded', type=release_downloaded_enum, default='all',
                                 help='Filter between {0}'.format(' ,'.join(release_downloaded_enum_list)))


@api.response(404, 'Show ID not found')
@api.response(414, 'Episode ID not found')
@api.response(400, 'Episode with ep_ids does not belong to show with show_id')
@series_api.route('/<int:show_id>/episodes/<int:ep_id>/releases')
@api.doc(params={'show_id': 'ID of the show', 'ep_id': 'Episode ID'})
@api.doc(parser=release_list_parser)
class SeriesReleasesAPI(APIResource):
    @api.response(200, 'Releases retrieved successfully for episode', release_list_schema)
    def get(self, show_id, ep_id, session):
        """ Get all episodes releases by show ID and episode ID """
        try:
            show = show_by_id(show_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Show with ID %s not found' % show_id
                    }, 404
        try:
            episode = episode_by_id(ep_id, session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Episode with ID %s not found' % ep_id
                    }, 414
        if not episode_in_show(show_id, ep_id):
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
            show = show_by_id(show_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Show with ID %s not found' % show_id
                    }, 404
        try:
            episode = episode_by_id(ep_id, session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Episode with ID %s not found' % ep_id
                    }, 414
        if not episode_in_show(show_id, ep_id):
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
            delete_release_by_id(release.id)
        return {'status': 'success',
                'message': 'Successfully deleted %s releases for episode %s and show %s' % (
                    number_of_releases, ep_id, show_id)}


@api.response(404, 'Show ID not found')
@api.response(414, 'Episode ID not found')
@api.response(424, 'Release ID not found')
@api.response(400, 'Episode with ep_id does not belong to show with show_id')
@api.response(410, 'Release with rel_id does not belong to episode with ep_id')
@series_api.route('/<int:show_id>/episodes/<int:ep_id>/releases/<int:rel_id>/')
@api.doc(params={'show_id': 'ID of the show', 'ep_id': 'Episode ID', 'rel_id': 'Release ID'})
class SeriesReleaseAPI(APIResource):
    @api.response(200, 'Release retrieved successfully for episode')
    def get(self, show_id, ep_id, rel_id, session):
        ''' Get episode release by show ID, episode ID and release ID '''
        try:
            show = show_by_id(show_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Show with ID %s not found' % show_id
                    }, 404
        try:
            episode = episode_by_id(ep_id, session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Episode with ID %s not found' % ep_id
                    }, 414
        try:
            release = release_by_id(rel_id, session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Release with ID %s not found' % rel_id
                    }, 424
        if not episode_in_show(show_id, ep_id):
            return {'status': 'error',
                    'message': 'Episode with id %s does not belong to show %s' % (ep_id, show_id)}, 400
        if not release_in_episode(ep_id, rel_id):
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
            show = show_by_id(show_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Show with ID %s not found' % show_id
                    }, 404
        try:
            episode = episode_by_id(ep_id, session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Episode with ID %s not found' % ep_id
                    }, 414
        try:
            release = release_by_id(rel_id, session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Release with ID %s not found' % rel_id
                    }, 424
        if not episode_in_show(show_id, ep_id):
            return {'status': 'error',
                    'message': 'Episode with id %s does not belong to show %s' % (ep_id, show_id)}, 400
        if not release_in_episode(ep_id, rel_id):
            return {'status': 'error',
                    'message': 'Release with id %s does not belong to episode %s' % (rel_id, ep_id)}, 410

        delete_release_by_id(rel_id)
        return {'status': 'success',
                'message': 'Successfully deleted release %s for episode %s and show %s' % (rel_id, ep_id, show_id)}
