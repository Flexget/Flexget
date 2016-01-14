from __future__ import unicode_literals, division, absolute_import

from math import ceil
from operator import itemgetter

from flask_restful import inputs
from sqlalchemy.orm.exc import NoResultFound

from flexget.api import api, APIResource, jsonify
from flexget.plugins.filter.series import get_latest_release, new_eps_after, get_series_summary, \
    Series, normalize_series_name, shows_by_name, show_by_id, forget_series_episode, forget_series, \
    set_series_begin

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
        'releases_id': {'type': 'integer'},
        'release_quality': {'type': 'string'}
    }
}

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
            rel = {
                'releases_id': release.id,
                'release_quality': release.quality.name
            }
            downloaded_releases.append(rel)
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


def get_episode_details(episode):
    releases = []

    episode_item = {
        'identifier': episode.identifier,
        'identifier_type': episode.identified_by,
        'download_age': episode.age
    }

    for release in episode.releases:
        rel = {
            'quality': release.quality.name,
            'title': release.title,
            'proper_count': release.proper_count,
            'downloaded': release.downloaded
        }
        releases.append(rel)
    episode_item['releases'] = releases
    return episode_item


series_list_schema = api.schema('list_series', series_list_schema)

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
series_list_parser.add_argument('sort_by', type=series_list_sort_value_enum, default='show_name',
                                help="Sort response by {0}. Default is show_name.".format(
                                        ' ,'.join(series_list_sort_value_enum_list)))
series_list_parser.add_argument('order', type=series_list_sort_order_enum, default='desc',
                                help="Sorting order. One of {0}. Default is desc".format(
                                        ' ,'.join(series_list_sort_order_enum_list)))


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
        sort_by = args['sort_by']
        order = args['order']
        # In case the default 'desc' order was received
        if order == 'desc':
            order = True

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

        sorted_show_list = sorted(shows, key=itemgetter(sort_by), reverse=order)

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


show_forget_parser = api.parser()
show_forget_parser.add_argument('ep_id', help="Episode ID to start getting the series from (e.g. S02E01, 2013-12-11,"
                                              " or 9, depending on how the series is numbered")

show_begin_parser = api.parser()
show_begin_parser.add_argument('ep_id', required=True, help="Episode ID to start getting the series"
                                                            " from (e.g. S02E01, 2013-12-11,4 or 9, "
                                                            "depending on how the series is numbered")


@series_api.route('/<int:show_id>')
class SeriesShowDetailsAPI(APIResource):
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

    @api.response(200, 'Removed series or episode from DB')
    @api.response(400, 'Unrecognized ep_id')
    @api.response(404, 'Show ID not found')
    @api.doc(parser=show_forget_parser)
    def delete(self, show_id, session):
        """ Remove episode or series from DB """
        try:
            show = show_by_id(show_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Show with ID %s not found' % show_id
                    }, 404

        args = show_forget_parser.parse_args()
        ep_id = args.get('ep_id')
        name = show.name
        if ep_id:
            try:
                forget_series_episode(name, ep_id)
            except ValueError:
                try:
                    forget_series_episode(name, ep_id.upper())
                except ValueError as e:
                    return {'status': 'error',
                            'message': e.args[0]
                            }, 400

            return {'status': 'success',
                    'message': 'successfully removed episode `%s` from series `%s`' % (ep_id, name)
                    }, 200

        else:
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
    @api.response(400, 'Unrecognized ep_id')
    @api.response(404, 'Show ID not found')
    @api.doc(parser=show_begin_parser)
    def put(self, show_id, session):
        """ Set the initial episode of an existing show """
        try:
            show = show_by_id(show_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Show with ID %s not found' % show_id
                    }, 404

        args = show_begin_parser.parse_args()
        ep_id = args.get('ep_id')
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
    @api.doc(parser=show_begin_parser)
    def post(self, name, session):
        """ Create a new show and set its first accepted episode """
        normalized_name = normalize_series_name(name)
        matches = shows_by_name(normalized_name, session=session)
        if matches:
            return {'status': 'error',
                    'message': 'Show `%s` already exist in DB' % name
                    }, 500
        show = Series()
        show.name = name
        session.add(show)

        args = show_begin_parser.parse_args()
        ep_id = args.get('ep_id')
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
