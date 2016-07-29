from __future__ import unicode_literals, division, absolute_import

import copy
from math import ceil

from builtins import *  # pylint: disable=unused-import, redefined-builtin
from flask import jsonify
from flask import request
from flask_restplus import inputs
from sqlalchemy.orm.exc import NoResultFound

from flexget.api import api, APIResource, ApiClient
from flexget.event import fire_event
from flexget.plugin import PluginError
from flexget.plugins.filter import series

series_api = api.namespace('series', description='Flexget Series operations')

default_error_schema = {
    'type': 'object',
    'properties': {
        'status': {'type': 'string'},
        'message': {'type': 'string'}
    }
}

default_error_schema = api.schema('default_error_schema', default_error_schema)

empty_response = api.schema('empty', {'type': 'object'})

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
        'release_first_seen': {'type': 'string', 'format': 'date-time'},
        'release_episode_id': {'type': 'integer'}
    }
}

release_schema = {
    'type': 'object',
    'properties': {
        'show': {'type': 'string'},
        'show_id': {'type': 'integer'},
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
        "episode_first_seen": {'type': 'string', 'format': 'date-time'},
        "episode_id": {'type': 'string'},
        "episode_identified_by": {'type': 'string'},
        "episode_identifier": {'type': 'string'},
        "episode_premiere_type": {'type': 'string'},
        "episode_number": {'type': 'string'},
        "episode_season": {'type': 'string'},
        "episode_series_id": {'type': 'string'},
        "episode_number_of_releases": {'type': 'integer'}
    }
}

show_object = {
    'type': 'object',
    'properties': {
        'show_id': {'type': 'integer'},
        'show_name': {'type': 'string'},
        'alternate_names': {'type': 'array', 'items': {'type': 'string'}},
        'begin_episode': begin_object,
        'latest_downloaded_episode': latest_object,
        'in_tasks': {'type': 'array', 'items': {'type': 'string'}}
    }
}

series_list_schema = {
    'type': 'object',
    'properties': {
        'shows': {
            'type': 'array',
            'items': show_object
        },
        'total_number_of_shows': {'type': 'integer'},
        'page_size': {'type': 'integer'},
        'total_number_of_pages': {'type': 'integer'},
        'page': {'type': 'integer'}
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
        'total_number_of_episodes': {'type': 'integer'},
        'page': {'type': 'integer'},
        'total_number_of_pages': {'type': 'integer'},
        'show_id': {'type': 'integer'},
        'show': {'type': 'string'}
    }
}

episode_list_schema = api.schema('episode_list', episode_list_schema)

episode_schema = {
    'type': 'object',
    'properties': {
        'episode': episode_object,
        'show_id': {'type': 'integer'},
        'show': {'type': 'string'}
    }
}
episode_schema = api.schema('episode_item', episode_schema)

series_edit_object = {
    'type': 'object',
    'properties': {
        'episode_identifier': {'type': 'string'},
        'alternate_names': {'type': 'array', 'items': {'type': 'string'}}
    },
    'anyOf': [
        {'required': ['episode_identifier']},
        {'required': ['alternate_names']}
    ],
    'additionalProperties:': False
}
series_edit_schema = api.schema('series_edit_schema', series_edit_object)

series_input_object = copy.deepcopy(series_edit_object)
series_input_object['properties']['series_name'] = {'type': 'string'}
del series_input_object['anyOf']
series_input_object['required'] = ['series_name']

series_input_schema = api.schema('series_input_schema', series_input_object)

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
        'episode_premiere_type': episode.is_premiere,
        'episode_number_of_releases': len(episode.releases)
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
        'alternate_names': [n.alt_name for n in show.alternate_names],
        'begin_episode': begin,
        'latest_downloaded_episode': latest,
        'in_tasks': [_show.name for _show in show.in_tasks]
    }
    return show_item


show_details_schema = api.schema('show_details', show_details_schema)
shows_schema = api.schema('list_of_shows', shows_schema)

series_list_parser = api.parser()
series_list_parser.add_argument('in_config', choices=('configured', 'unconfigured', 'all'), default='configured',
                                help="Filter list if shows are currently in configuration.")
series_list_parser.add_argument('premieres', type=inputs.boolean, default=False,
                                help="Filter by downloaded premieres only.")
series_list_parser.add_argument('status', choices=('new', 'stale'), help="Filter by status")
series_list_parser.add_argument('days', type=int,
                                help="Filter status by number of days.")
series_list_parser.add_argument('page', type=int, default=1, help='Page number. Default is 1')
series_list_parser.add_argument('page_size', type=int, default=10, help='Shows per page. Max is 100.')

series_list_parser.add_argument('sort_by', choices=('show_name', 'last_download_date'),
                                default='last_download_date',
                                help="Sort response by attribute.")
series_list_parser.add_argument('descending', type=inputs.boolean, default=True, store_missing=True,
                                help="Sorting order.")
series_list_parser.add_argument('lookup', choices=('tvdb', 'tvmaze'), action='append',
                                help="Get lookup result for every show by sending another request to lookup API")

ep_identifier_doc = "'episode_identifier' should be one of SxxExx, integer or date formatted such as 2012-12-12"


@series_api.route('/')
class SeriesListAPI(APIResource):
    @api.response(404, 'Page does not exist', default_error_schema)
    @api.response(200, 'Series list retrieved successfully', series_list_schema)
    @api.doc(parser=series_list_parser, description="Get a  list of Flexget's shows in DB")
    def get(self, session=None):
        """ List existing shows """
        args = series_list_parser.parse_args()
        page = args['page']
        page_size = args['page_size']
        lookup = args.get('lookup')

        # Handle max size limit
        if page_size > 100:
            page_size = 100

        start = page_size * (page - 1)
        stop = start + page_size

        kwargs = {
            'configured': args.get('in_config'),
            'premieres': args.get('premieres'),
            'status': args.get('status'),
            'days': args.get('days'),
            'start': start,
            'stop': stop,
            'sort_by': args.get('sort_by'),
            'descending': args.get('descending'),
            'session': session

        }
        num_of_shows = series.get_series_summary(count=True, **kwargs)

        raw_series_list = series.get_series_summary(**kwargs)
        converted_series_list = [get_series_details(show) for show in raw_series_list]

        pages = int(ceil(num_of_shows / float(page_size)))

        if page > pages and pages != 0:
            return {'error': 'page %s does not exist' % page}, 404

        number_of_shows = min(page_size, num_of_shows)

        response = {
            'shows': converted_series_list,
            'page_size': number_of_shows,
            'total_number_of_shows': num_of_shows,
            'page': page,
            'total_number_of_pages': pages
        }

        if lookup:
            api_client = ApiClient()
            for endpoint in lookup:
                base_url = '/%s/series/' % endpoint
                for show in response['shows']:
                    pos = response['shows'].index(show)
                    response['shows'][pos].setdefault('lookup', {})
                    url = base_url + show['show_name'] + '/'
                    result = api_client.get_endpoint(url)
                    response['shows'][pos]['lookup'].update({endpoint: result})
        return jsonify(response)

    @api.response(200, 'Adding series and setting first accepted episode to ep_id', show_details_schema)
    @api.response(500, 'Show already exists', default_error_schema)
    @api.response(501, 'Episode Identifier format is incorrect', default_error_schema)
    @api.response(502, 'Alternate name already exist for a different show', default_error_schema)
    @api.validate(series_input_schema, description=ep_identifier_doc)
    def post(self, session):
        """ Create a new show and set its first accepted episode and/or alternate names """
        data = request.json
        series_name = data.get('series_name')

        normalized_name = series.normalize_series_name(series_name)
        matches = series.shows_by_exact_name(normalized_name, session=session)
        if matches:
            return {'status': 'error',
                    'message': 'Show `%s` already exist in DB' % series_name
                    }, 500
        show = series.Series()
        show.name = series_name
        session.add(show)

        ep_id = data.get('episode_identifier')
        alt_names = data.get('alternate_names')
        if ep_id:
            try:
                series.set_series_begin(show, ep_id)
            except ValueError as e:
                return {'status': 'error',
                        'message': e.args[0]
                        }, 501
        if alt_names:
            try:
                series.set_alt_names(alt_names, show, session)
            except PluginError as e:
                return {'status': 'error',
                        'message': e.value
                        }, 502

        return jsonify(get_series_details(show))


@series_api.route('/search/<string:name>/')
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


delete_parser = api.parser()
delete_parser.add_argument('forget', type=inputs.boolean, default=False,
                           help="Enabling this will fire a 'forget' event that will delete the downloaded releases "
                                "from the entire DB, enabling to re-download them")


@series_api.route('/<int:show_id>/')
@api.doc(params={'show_id': 'ID of the show'})
class SeriesShowAPI(APIResource):
    @api.response(404, 'Show ID not found', default_error_schema)
    @api.response(200, 'Show information retrieved successfully', show_details_schema)
    @api.doc(description='Get a specific show using its ID')
    def get(self, show_id, session):
        """ Get show details by ID """
        try:
            show = series.show_by_id(show_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Show with ID %s not found' % show_id
                    }, 404

        show = get_series_details(show)

        return jsonify(show)

    @api.response(200, 'Removed series from DB', empty_response)
    @api.response(404, 'Show ID not found', default_error_schema)
    @api.doc(description='Delete a specific show using its ID',
             parser=delete_parser)
    def delete(self, show_id, session):
        """ Remove series from DB """
        try:
            show = series.show_by_id(show_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Show with ID %s not found' % show_id
                    }, 404

        name = show.name
        args = delete_parser.parse_args()
        try:
            series.remove_series(name, forget=args.get('forget'))
        except ValueError as e:
            return {'status': 'error',
                    'message': e.args[0]
                    }, 404
        return {}

    @api.response(200, 'Episodes for series will be accepted starting with ep_id', show_details_schema)
    @api.response(404, 'Show ID not found', default_error_schema)
    @api.response(501, 'Episode Identifier format is incorrect', default_error_schema)
    @api.response(502, 'Alternate name already exist for a different show', default_error_schema)
    @api.validate(series_edit_schema, description=ep_identifier_doc)
    @api.doc(description='Set a begin episode or alternate names using a show ID. Note that alternate names override '
                         'the existing names (if name does not belong to a different show).')
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
        alt_names = data.get('alternate_names')
        if ep_id:
            try:
                series.set_series_begin(show, ep_id)
            except ValueError as e:
                return {'status': 'error',
                        'message': e.args[0]
                        }, 501
        if alt_names:
            try:
                series.set_alt_names(alt_names, show, session)
            except PluginError as e:
                return {'status': 'error',
                        'message': e.value
                        }, 502

        return jsonify(get_series_details(show))


episode_parser = api.parser()
episode_parser.add_argument('page', type=int, default=1, help='Page number. Default is 1')
episode_parser.add_argument('page_size', type=int, default=10, help='Shows per page. Max is 100.')
episode_parser.add_argument('order', choices=('desc', 'asc'), default='desc', help="Sorting order.")


@api.response(404, 'Show ID not found', default_error_schema)
@series_api.route('/<int:show_id>/episodes/')
@api.doc(params={'show_id': 'ID of the show'})
class SeriesEpisodesAPI(APIResource):
    @api.response(200, 'Episodes retrieved successfully for show', episode_list_schema)
    @api.response(405, 'Page does not exists', model=default_error_schema)
    @api.doc(description='Get all show episodes via its ID', parser=episode_parser)
    def get(self, show_id, session):
        """ Get episodes by show ID """
        args = episode_parser.parse_args()
        page = args['page']
        page_size = args['page_size']

        # Handle max size limit
        if page_size > 100:
            page_size = 100

        order = args['order']
        # In case the default 'desc' order was received
        descending = bool(order == 'desc')

        start = page_size * (page - 1)
        stop = start + page_size

        kwargs = {
            'start': start,
            'stop': stop,
            'descending': descending,
            'session': session
        }

        try:
            show = series.show_by_id(show_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Show with ID %s not found' % show_id
                    }, 404
        count = series.show_episodes(show, count=True, session=session)
        episodes = [get_episode_details(episode) for episode in series.show_episodes(show, **kwargs)]
        pages = int(ceil(count / float(page_size)))

        if page > pages and pages != 0:
            return {'status': 'error',
                    'message': 'page does not exist' % show_id
                    }, 500

        return jsonify({'show': show.name,
                        'show_id': show_id,
                        'number_of_episodes': len(episodes),
                        'episodes': episodes,
                        'total_number_of_episodes': count,
                        'page': page,
                        'total_number_of_pages': pages})

    @api.response(500, 'Error when trying to forget episode', default_error_schema)
    @api.response(200, 'Successfully forgotten all episodes from show', empty_response)
    @api.doc(description='Delete all show episodes via its ID. Deleting an episode will mark it as wanted again',
             parser=delete_parser)
    def delete(self, show_id, session):
        """ Deletes all episodes of a show"""
        try:
            show = series.show_by_id(show_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Show with ID %s not found' % show_id
                    }, 404
        name = show.name
        args = delete_parser.parse_args()
        try:
            series.remove_series(name, forget=args.get('forget'))
        except ValueError as e:
            return {'status': 'error',
                    'message': e.args[0]
                    }, 404
        return {}


@api.response(404, 'Show ID not found', default_error_schema)
@api.response(414, 'Episode ID not found', default_error_schema)
@api.response(400, 'Episode with ep_ids does not belong to show with show_id', default_error_schema)
@series_api.route('/<int:show_id>/episodes/<int:ep_id>/')
@api.doc(params={'show_id': 'ID of the show', 'ep_id': 'Episode ID'})
class SeriesEpisodeAPI(APIResource):
    @api.response(200, 'Episode retrieved successfully for show', episode_schema)
    @api.doc(description='Get a specific episode via its ID and show ID')
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

    @api.response(200, 'Episode successfully forgotten for show', empty_response)
    @api.doc(description='Delete a specific episode via its ID and show ID. Deleting an episode will mark it as '
                         'wanted again',
             parser=delete_parser)
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

        args = delete_parser.parse_args()
        try:
            series.remove_series_episode(show.name, episode.identifier, args.get('forget'))
        except ValueError as e:
            return {'status': 'error',
                    'message': e.args[0]
                    }, 404
        return {}


release_list_parser = api.parser()
release_list_parser.add_argument('downloaded', type=inputs.boolean, help='Filter between release status')

release_delete_parser = release_list_parser.copy()
release_delete_parser.add_argument('forget', type=inputs.boolean, default=False,
                                   help="Enabling this will for 'forget' event that will delete the downloaded"
                                        " releases from the entire DB, enabling to re-download them")


@api.response(404, 'Show ID not found', default_error_schema)
@api.response(414, 'Episode ID not found', default_error_schema)
@api.response(400, 'Episode with ep_ids does not belong to show with show_id', default_error_schema)
@series_api.route('/<int:show_id>/episodes/<int:ep_id>/releases/')
@api.doc(params={'show_id': 'ID of the show', 'ep_id': 'Episode ID'},
         description='Releases are any seen entries that match the episode. ')
class SeriesReleasesAPI(APIResource):
    @api.response(200, 'Releases retrieved successfully for episode', release_list_schema)
    @api.doc(description='Get all matching releases for a specific episode of a specific show.',
             parser=release_list_parser)
    def get(self, show_id, ep_id, session):
        """ Get all episodes releases by show ID and episode ID """
        try:
            series.show_by_id(show_id, session=session)
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
        downloaded = args.get('downloaded') == True if args.get('downloaded') is not None else None
        release_items = []
        for release in episode.releases:
            if downloaded and release.downloaded or downloaded is False and not release.downloaded or not downloaded:
                release_items.append(get_release_details(release))

        return jsonify({
            'releases': release_items,
            'number_of_releases': len(release_items),
            'episode_id': ep_id,
            'show_id': show_id

        })

    @api.response(200, 'Successfully deleted all releases for episode', empty_response)
    @api.doc(description='Delete all releases for a specific episode of a specific show.',
             parser=release_delete_parser)
    def delete(self, show_id, ep_id, session):
        """ Deletes all episodes releases by show ID and episode ID """
        try:
            series.show_by_id(show_id, session=session)
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

        args = release_delete_parser.parse_args()
        downloaded = args.get('downloaded') == True if args.get('downloaded') is not None else None
        release_items = []
        for release in episode.releases:
            if downloaded and release.downloaded or downloaded is False and not release.downloaded or not downloaded:
                release_items.append(release)
            if args.get('delete_seen'):
                fire_event('forget', release.title)

        for release in release_items:
            series.delete_release_by_id(release.id)
        return {}

    @api.response(200, 'Successfully reset all downloaded releases for episode', empty_response)
    @api.doc(description='Resets all of the downloaded releases of an episode, clearing the quality to be downloaded '
                         'again,')
    def put(self, show_id, ep_id, session):
        """ Marks all downloaded releases as not downloaded """
        try:
            series.show_by_id(show_id, session=session)
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

        for release in episode.releases:
            if release.downloaded:
                release.downloaded = False

        return {}


@api.response(404, 'Show ID not found', default_error_schema)
@api.response(414, 'Episode ID not found', default_error_schema)
@api.response(424, 'Release ID not found', default_error_schema)
@api.response(400, 'Episode with ep_id does not belong to show with show_id', default_error_schema)
@api.response(410, 'Release with rel_id does not belong to episode with ep_id', default_error_schema)
@series_api.route('/<int:show_id>/episodes/<int:ep_id>/releases/<int:rel_id>/')
@api.doc(params={'show_id': 'ID of the show', 'ep_id': 'Episode ID', 'rel_id': 'Release ID'})
class SeriesReleaseAPI(APIResource):
    @api.response(200, 'Release retrieved successfully for episode', release_schema)
    @api.doc(description='Get a specific downloaded release for a specific episode of a specific show')
    def get(self, show_id, ep_id, rel_id, session):
        ''' Get episode release by show ID, episode ID and release ID '''
        try:
            show = series.show_by_id(show_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Show with ID %s not found' % show_id
                    }, 404
        try:
            series.episode_by_id(ep_id, session)
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
                    'message': 'Release id %s does not belong to episode %s' % (rel_id, ep_id)}, 410

        return jsonify({
            'show': show.name,
            'show_id': show_id,
            'episode_id': ep_id,
            'release': get_release_details(release)
        })

    @api.response(200, 'Release successfully deleted', empty_response)
    @api.doc(description='Delete a specific releases for a specific episode of a specific show.',
             parser=delete_parser)
    def delete(self, show_id, ep_id, rel_id, session):
        ''' Delete episode release by show ID, episode ID and release ID '''
        try:
            series.show_by_id(show_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Show with ID %s not found' % show_id
                    }, 404
        try:
            series.episode_by_id(ep_id, session)
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
        args = delete_parser.parse_args()
        if args.get('delete_seen'):
            fire_event('forget', release.title)

        series.delete_release_by_id(rel_id)
        return {}

    @api.response(200, 'Successfully reset downloaded release status', empty_response)
    @api.response(500, 'Release is not marked as downloaded', default_error_schema)
    @api.doc(description='Resets the downloaded release status, clearing the quality to be downloaded again')
    def put(self, show_id, ep_id, rel_id, session):
        """ Resets a downloaded release status """
        try:
            series.show_by_id(show_id, session=session)
        except NoResultFound:
            return {'status': 'error',
                    'message': 'Show with ID %s not found' % show_id
                    }, 404
        try:
            series.episode_by_id(ep_id, session)
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
        if not release.downloaded:
            return {'status': 'error',
                    'message': 'Release with id %s is not set as downloaded' % rel_id}, 500

        release.downloaded = False
        return {}
