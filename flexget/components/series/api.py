import copy
from math import ceil

from flask import jsonify, request
from flask_restx import inputs
from sqlalchemy.orm.exc import NoResultFound

from flexget import plugin
from flexget.api import APIClient, APIResource, api
from flexget.api.app import (
    BadRequest,
    Conflict,
    NotFoundError,
    base_message_schema,
    etag,
    pagination_headers,
    success_response,
)
from flexget.event import fire_event
from flexget.plugin import PluginError

from . import db
from .utils import normalize_series_name

try:
    # NOTE: Importing other plugins is discouraged!
    from flexget.components.thetvdb.api import ObjectsContainer as tvdb
except ImportError:
    raise plugin.DependencyError(issued_by=__name__, missing='tvdb_lookup')


try:
    # NOTE: Importing other plugins is discouraged!
    from flexget.components.tvmaze.api import ObjectsContainer as tvmaze
except ImportError:
    raise plugin.DependencyError(issued_by=__name__, missing='tvmaze_lookup')

series_api = api.namespace('series', description='FlexGet Series operations')


def series_details(show, begin=False, latest=False):
    series_dict = {
        'id': show.id,
        'name': show.name,
        'alternate_names': [n.alt_name for n in show.alternate_names],
        'in_tasks': [_show.name for _show in show.in_tasks],
    }
    if begin:
        series_dict['begin_episode'] = show.begin.to_dict() if show.begin else None
    if latest:
        latest_entity = db.get_latest_release(show)
        series_dict['latest_entity'] = latest_entity.to_dict() if latest_entity else None
        if latest_entity:
            series_dict['latest_entity']['latest_release'] = latest_entity.latest_release.to_dict()
    return series_dict


class ObjectsContainer:
    episode_release_object = {
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'},
            'title': {'type': 'string'},
            'downloaded': {'type': 'boolean'},
            'quality': {'type': 'string'},
            'proper_count': {'type': 'integer'},
            'first_seen': {'type': 'string', 'format': 'date-time'},
            'episode_id': {'type': 'integer'},
        },
        'required': [
            'id',
            'title',
            'downloaded',
            'quality',
            'proper_count',
            'first_seen',
            'episode_id',
        ],
    }

    season_release_object = copy.deepcopy(episode_release_object)
    del season_release_object['properties']['episode_id']
    season_release_object['properties']['season_id'] = {'type': 'integer'}
    season_release_object['required'].remove('episode_id')
    season_release_object['required'].append('season_id')

    episode_release_list_schema = {'type': 'array', 'items': episode_release_object}
    season_release_list_schema = {'type': 'array', 'items': season_release_object}

    episode_object = {
        'type': ['object', 'null'],
        'properties': {
            "first_seen": {'type': ['string', 'null'], 'format': 'date-time'},
            "id": {'type': 'integer'},
            "identified_by": {'type': 'string'},
            "identifier": {'type': 'string'},
            "premiere": {'type': ['string', 'boolean']},
            "number": {'type': 'integer'},
            "season": {'type': 'integer'},
            "series_id": {'type': 'integer'},
            "number_of_releases": {'type': 'integer'},
            'latest_release': episode_release_object,
        },
        'required': [
            'first_seen',
            'id',
            'identified_by',
            'identifier',
            'premiere',
            'number',
            'season',
            'series_id',
            'number_of_releases',
        ],
    }

    season_object = copy.deepcopy(episode_object)
    del season_object['properties']['number']
    season_object['required'].remove('number')
    season_object['required'].remove('premiere')

    single_series_object = {
        'type': 'object',
        'properties': {
            'id': {'type': 'integer'},
            'name': {'type': 'string'},
            'alternate_names': {'type': 'array', 'items': {'type': 'string'}},
            'in_tasks': {'type': 'array', 'items': {'type': 'string'}},
            'lookup': {
                'type': 'object',
                'properties': {
                    'tvmaze': tvmaze.tvmaze_series_object,
                    'tvdb': tvdb.tvdb_series_object,
                },
            },
            'latest_episode': episode_object,
            'begin_episode': episode_object,
        },
        'required': ['id', 'name', 'alternate_names', 'in_tasks'],
    }

    series_list_schema = {'type': 'array', 'items': single_series_object}

    episode_list_schema = {'type': 'array', 'items': episode_object}

    seasons_list_schema = {'type': 'array', 'items': season_object}

    series_edit_object = {
        'type': 'object',
        'properties': {
            'begin_episode': {'type': ['string', 'integer'], 'format': 'episode_or_season_id'},
            'alternate_names': {'type': 'array', 'items': {'type': 'string'}},
        },
        'anyOf': [{'required': ['begin_episode']}, {'required': ['alternate_names']}],
        'additionalProperties:': False,
    }

    series_input_object = copy.deepcopy(series_edit_object)
    series_input_object['properties']['name'] = {'type': 'string'}
    del series_input_object['anyOf']
    series_input_object['required'] = ['name']


series_list_schema = api.schema_model('list_series', ObjectsContainer.series_list_schema)
series_edit_schema = api.schema_model('series_edit_schema', ObjectsContainer.series_edit_object)
series_input_schema = api.schema_model('series_input_schema', ObjectsContainer.series_input_object)
show_details_schema = api.schema_model('show_details', ObjectsContainer.single_series_object)

episode_list_schema = api.schema_model('episode_list', ObjectsContainer.episode_list_schema)
episode_schema = api.schema_model('episode_item', ObjectsContainer.episode_object)

season_list_schema = api.schema_model('season_list', ObjectsContainer.seasons_list_schema)
season_schema = api.schema_model('episode_item', ObjectsContainer.season_object)

episode_release_schema = api.schema_model(
    'release_schema', ObjectsContainer.episode_release_object
)
episode_release_list_schema = api.schema_model(
    'release_list_schema', ObjectsContainer.episode_release_list_schema
)

season_release_schema = api.schema_model('release_schema', ObjectsContainer.season_release_object)
season_release_list_schema = api.schema_model(
    'release_list_schema', ObjectsContainer.season_release_list_schema
)

base_series_parser = api.parser()
base_series_parser.add_argument(
    'begin', type=inputs.boolean, default=True, help='Show series begin episode'
)
base_series_parser.add_argument(
    'latest',
    type=inputs.boolean,
    default=True,
    help='Show series latest downloaded episode and release',
)

sort_choices = ('show_name', 'last_download_date')
series_list_parser = api.pagination_parser(base_series_parser, sort_choices=sort_choices)
series_list_parser.add_argument(
    'in_config',
    choices=('configured', 'unconfigured', 'all'),
    default='configured',
    help="Filter list if shows are currently in configuration.",
)
series_list_parser.add_argument(
    'premieres', type=inputs.boolean, default=False, help="Filter by downloaded premieres only."
)
series_list_parser.add_argument(
    'lookup',
    choices=('tvdb', 'tvmaze'),
    action='append',
    help="Get lookup result for every show by sending another request to lookup API",
)
series_list_parser.add_argument('query', help="Search by name based on the query")

ep_identifier_doc = (
    "'episode_identifier' should be one of SxxExx, integer or date formatted such as 2012-12-12"
)


@series_api.route('/')
class SeriesAPI(APIResource):
    @etag
    @api.response(200, 'Series list retrieved successfully', series_list_schema)
    @api.response(NotFoundError)
    @api.doc(parser=series_list_parser, description="Get a  list of Flexget's shows in DB")
    def get(self, session=None):
        """List existing shows"""
        args = series_list_parser.parse_args()

        # Filter params
        configured = args['in_config']
        premieres = args['premieres']

        # Pagination and sorting params
        page = args['page']
        per_page = args['per_page']
        sort_by = args['sort_by']
        sort_order = args['order']
        name = normalize_series_name(args['query']) if args['query'] else None

        # Handle max size limit
        if per_page > 100:
            per_page = 100

        descending = sort_order == 'desc'

        # Data params
        lookup = args.get('lookup')
        begin = args.get('begin')
        latest = args.get('latest')

        start = per_page * (page - 1)
        stop = start + per_page

        kwargs = {
            'configured': configured,
            'premieres': premieres,
            'start': start,
            'stop': stop,
            'sort_by': sort_by,
            'descending': descending,
            'session': session,
            'name': name,
        }

        total_items = db.get_series_summary(count=True, **kwargs)

        if not total_items:
            return jsonify([])

        series_list = []
        for s in db.get_series_summary(**kwargs):
            series_object = series_details(s, begin, latest)
            series_list.append(series_object)

        # Total number of pages
        total_pages = int(ceil(total_items / float(per_page)))

        if total_pages < page and total_pages != 0:
            raise NotFoundError('page %s does not exist' % page)

        # Actual results in page
        actual_size = min(per_page, len(series_list))

        # Do relevant lookups
        if lookup:
            api_client = APIClient()
            for endpoint in lookup:
                base_url = '/%s/series/' % endpoint
                for show in series_list:
                    pos = series_list.index(show)
                    series_list[pos].setdefault('lookup', {})
                    url = base_url + show['name'] + '/'
                    result = api_client.get_endpoint(url)
                    series_list[pos]['lookup'].update({endpoint: result})

        # Get pagination headers
        pagination = pagination_headers(total_pages, total_items, actual_size, request)

        # Created response
        rsp = jsonify(series_list)

        # Add link header to response
        rsp.headers.extend(pagination)
        return rsp

    @api.response(201, model=show_details_schema)
    @api.response(Conflict)
    @api.validate(series_input_schema, description=ep_identifier_doc)
    def post(self, session):
        """Create a new show and set its first accepted episode and/or alternate names"""
        data = request.json
        series_name = data.get('name')

        normalized_name = normalize_series_name(series_name)
        matches = db.shows_by_exact_name(normalized_name, session=session)
        if matches:
            raise Conflict('Show `%s` already exist in DB' % series_name)
        show = db.Series()
        show.name = series_name
        session.add(show)

        ep_id = data.get('begin_episode')
        alt_names = data.get('alternate_names')
        if ep_id:
            db.set_series_begin(show, ep_id)
        if alt_names:
            try:
                db.set_alt_names(alt_names, show, session)
            except PluginError as e:
                # Alternate name already exist for a different show
                raise Conflict(e.value)
        session.commit()
        rsp = jsonify(series_details(show, begin=ep_id is not None))
        rsp.status_code = 201
        return rsp


@series_api.route('/search/<string:name>/')
@api.doc(
    description='Searches for a show in the DB via its name. Returns a list of matching shows.'
)
class SeriesGetShowsAPI(APIResource):
    @etag
    @api.response(200, 'Show list retrieved successfully', series_list_schema)
    @api.doc(params={'name': 'Name of the show(s) to search'}, parser=base_series_parser)
    def get(self, name, session):
        """List of shows matching lookup name"""
        name = normalize_series_name(name)
        matches = db.shows_by_name(name, session=session)

        args = series_list_parser.parse_args()
        begin = args.get('begin')
        latest = args.get('latest')

        shows = []
        for match in matches:
            shows.append(series_details(match, begin, latest))

        return jsonify(shows)


delete_parser = api.parser()
delete_parser.add_argument(
    'forget',
    type=inputs.boolean,
    default=False,
    help="Enabling this will fire a 'forget' event that will delete the downloaded releases "
    "from the entire DB, enabling to re-download them",
)


@series_api.route('/<int:show_id>/')
@api.doc(params={'show_id': 'ID of the show'})
@api.response(NotFoundError)
class SeriesShowAPI(APIResource):
    @etag
    @api.response(200, 'Show information retrieved successfully', show_details_schema)
    @api.doc(description='Get a specific show using its ID', parser=base_series_parser)
    def get(self, show_id, session):
        """Get show details by ID"""
        try:
            show = db.show_by_id(show_id, session=session)
        except NoResultFound:
            raise NotFoundError('Show with ID %s not found' % show_id)

        args = series_list_parser.parse_args()
        begin = args.get('begin')
        latest = args.get('latest')

        return jsonify(series_details(show, begin, latest))

    @api.response(200, 'Removed series from DB', model=base_message_schema)
    @api.doc(description='Delete a specific show using its ID', parser=delete_parser)
    def delete(self, show_id, session):
        """Remove series from DB"""
        try:
            show = db.show_by_id(show_id, session=session)
        except NoResultFound:
            raise NotFoundError('Show with ID %s not found' % show_id)

        name = show.name
        args = delete_parser.parse_args()
        db.remove_series(name, forget=args.get('forget'))

        return success_response('successfully removed series %s from DB' % show_id)

    @api.response(
        200, 'Episodes for series will be accepted starting with ep_id', show_details_schema
    )
    @api.response(Conflict)
    @api.validate(series_edit_schema, description=ep_identifier_doc)
    @api.doc(
        description='Set a begin episode or alternate names using a show ID. Note that alternate names override '
        'the existing names (if name does not belong to a different show).'
    )
    def put(self, show_id, session):
        """Set the initial episode of an existing show"""
        try:
            show = db.show_by_id(show_id, session=session)
        except NoResultFound:
            raise NotFoundError('Show with ID %s not found' % show_id)
        data = request.json
        ep_id = data.get('begin_episode')
        alt_names = data.get('alternate_names')
        if ep_id:
            db.set_series_begin(show, ep_id)
        if alt_names:
            try:
                db.set_alt_names(alt_names, show, session)
            except PluginError as e:
                # Alternate name already exist for a different show
                raise Conflict(e.value)
        return jsonify(series_details(show, begin=ep_id is not None))


entity_parser = api.pagination_parser(add_sort=True)


@api.response(NotFoundError)
@series_api.route('/<int:show_id>/seasons/')
@api.doc(
    params={'show_id': 'ID of the show'},
    description='The \'Series-ID\' header will be appended to the result headers',
)
class SeriesSeasonsAPI(APIResource):
    @etag
    @api.response(200, 'Seasons retrieved successfully for show', season_list_schema)
    @api.doc(description='Get all show seasons via its ID', parser=entity_parser)
    def get(self, show_id, session):
        """Get seasons by show ID"""
        args = entity_parser.parse_args()

        # Pagination and sorting params
        page = args['page']
        per_page = args['per_page']
        sort_order = args['order']

        # Handle max size limit
        if per_page > 100:
            per_page = 100

        descending = sort_order == 'desc'

        start = per_page * (page - 1)
        stop = start + per_page

        kwargs = {'start': start, 'stop': stop, 'descending': descending, 'session': session}

        try:
            show = db.show_by_id(show_id, session=session)
        except NoResultFound:
            raise NotFoundError('show with ID %s not found' % show_id)

        total_items = db.show_seasons(show, count=True, session=session)

        if not total_items:
            return jsonify([])

        seasons = [season.to_dict() for season in db.show_seasons(show, **kwargs)]

        total_pages = int(ceil(total_items / float(per_page)))

        if total_pages < page and total_pages != 0:
            raise NotFoundError('page %s does not exist' % page)

        # Actual results in page
        actual_size = min(per_page, len(seasons))

        # Get pagination headers
        pagination = pagination_headers(total_pages, total_items, actual_size, request)

        # Created response
        rsp = jsonify(seasons)

        # Add link header to response
        rsp.headers.extend(pagination)

        # Add series ID header
        rsp.headers.extend({'Series-ID': show_id})
        return rsp

    @api.response(200, 'Successfully forgotten all seasons from show', model=base_message_schema)
    @api.doc(
        description='Delete all show seasons via its ID. Deleting a season will mark it as wanted again',
        parser=delete_parser,
    )
    def delete(self, show_id, session):
        """Deletes all seasons of a show"""
        try:
            show = db.show_by_id(show_id, session=session)
        except NoResultFound:
            raise NotFoundError('show with ID %s not found' % show_id)
        args = delete_parser.parse_args()
        forget = args.get('forget')
        for season in show.seasons:
            db.remove_series_entity(show.name, season.identifier, forget)
        return success_response('successfully removed all series %s seasons from DB' % show_id)


@api.response(NotFoundError)
@api.response(BadRequest)
@series_api.route('/<int:show_id>/seasons/<int:season_id>/')
@api.doc(params={'show_id': 'ID of the show', 'season_id': 'Season ID'})
class SeriesSeasonsAPI(APIResource):
    @etag
    @api.response(200, 'Season retrieved successfully for show', season_schema)
    @api.doc(description='Get a specific season via its ID and show ID')
    def get(self, show_id, season_id, session):
        """Get season by show ID and season ID"""
        try:
            db.show_by_id(show_id, session=session)
        except NoResultFound:
            raise NotFoundError('show with ID %s not found' % show_id)
        try:
            season = db.season_by_id(season_id, session)
        except NoResultFound:
            raise NotFoundError('season with ID %s not found' % season_id)
        if not db.season_in_show(show_id, season_id):
            raise BadRequest('season with id %s does not belong to show %s' % (season_id, show_id))

        rsp = jsonify(season.to_dict())

        # Add Series-ID header
        rsp.headers.extend({'Series-ID': show_id})
        return rsp

    @api.response(200, 'Season successfully forgotten for show', model=base_message_schema)
    @api.doc(
        description='Delete a specific season via its ID and show ID. Deleting a season will mark it as '
        'wanted again',
        parser=delete_parser,
    )
    def delete(self, show_id, season_id, session):
        """Forgets season by show ID and season ID"""
        try:
            show = db.show_by_id(show_id, session=session)
        except NoResultFound:
            raise NotFoundError('show with ID %s not found' % show_id)
        try:
            season = db.season_by_id(season_id, session)
        except NoResultFound:
            raise NotFoundError('season with ID %s not found' % season_id)
        if not db.season_in_show(show_id, season_id):
            raise BadRequest('season with id %s does not belong to show %s' % (season_id, show_id))

        args = delete_parser.parse_args()
        db.remove_series_entity(show.name, season.identifier, args.get('forget'))

        return success_response(
            'successfully removed season %s from show %s' % (season_id, show_id)
        )


@api.response(NotFoundError)
@series_api.route('/<int:show_id>/episodes/')
@api.doc(
    params={'show_id': 'ID of the show'},
    description='The \'Series-ID\' header will be appended to the result headers',
)
class SeriesEpisodesAPI(APIResource):
    @etag
    @api.response(200, 'Episodes retrieved successfully for show', episode_list_schema)
    @api.doc(description='Get all show episodes via its ID', parser=entity_parser)
    def get(self, show_id, session):
        """Get episodes by show ID"""
        args = entity_parser.parse_args()

        # Pagination and sorting params
        page = args['page']
        per_page = args['per_page']
        sort_order = args['order']

        # Handle max size limit
        if per_page > 100:
            per_page = 100

        descending = sort_order == 'desc'

        start = per_page * (page - 1)
        stop = start + per_page

        kwargs = {'start': start, 'stop': stop, 'descending': descending, 'session': session}

        try:
            show = db.show_by_id(show_id, session=session)
        except NoResultFound:
            raise NotFoundError('show with ID %s not found' % show_id)

        total_items = db.show_episodes(show, count=True, session=session)

        if not total_items:
            return jsonify([])

        episodes = [episode.to_dict() for episode in db.show_episodes(show, **kwargs)]

        total_pages = int(ceil(total_items / float(per_page)))

        if total_pages < page and total_pages != 0:
            raise NotFoundError('page %s does not exist' % page)

        # Actual results in page
        actual_size = min(per_page, len(episodes))

        # Get pagination headers
        pagination = pagination_headers(total_pages, total_items, actual_size, request)

        # Created response
        rsp = jsonify(episodes)

        # Add link header to response
        rsp.headers.extend(pagination)

        # Add series ID header
        rsp.headers.extend({'Series-ID': show_id})
        return rsp

    @api.response(200, 'Successfully forgotten all episodes from show', model=base_message_schema)
    @api.doc(
        description='Delete all show episodes via its ID. Deleting an episode will mark it as wanted again',
        parser=delete_parser,
    )
    def delete(self, show_id, session):
        """Deletes all episodes of a show"""
        try:
            show = db.show_by_id(show_id, session=session)
        except NoResultFound:
            raise NotFoundError('show with ID %s not found' % show_id)
        args = delete_parser.parse_args()
        forget = args.get('forget')
        for episode in show.episodes:
            db.remove_series_entity(show.name, episode.identifier, forget)
        return success_response('successfully removed all series %s episodes from DB' % show_id)


@api.response(NotFoundError)
@api.response(BadRequest)
@series_api.route('/<int:show_id>/episodes/<int:ep_id>/')
@api.doc(params={'show_id': 'ID of the show', 'ep_id': 'Episode ID'})
class SeriesEpisodeAPI(APIResource):
    @etag
    @api.response(200, 'Episode retrieved successfully for show', episode_schema)
    @api.doc(description='Get a specific episode via its ID and show ID')
    def get(self, show_id, ep_id, session):
        """Get episode by show ID and episode ID"""
        try:
            db.show_by_id(show_id, session=session)
        except NoResultFound:
            raise NotFoundError('show with ID %s not found' % show_id)
        try:
            episode = db.episode_by_id(ep_id, session)
        except NoResultFound:
            raise NotFoundError('episode with ID %s not found' % ep_id)
        if not db.episode_in_show(show_id, ep_id):
            raise BadRequest('episode with id %s does not belong to show %s' % (ep_id, show_id))

        rsp = jsonify(episode.to_dict())

        # Add Series-ID header
        rsp.headers.extend({'Series-ID': show_id})
        return rsp

    @api.response(200, 'Episode successfully forgotten for show', model=base_message_schema)
    @api.doc(
        description='Delete a specific episode via its ID and show ID. Deleting an episode will mark it as '
        'wanted again',
        parser=delete_parser,
    )
    def delete(self, show_id, ep_id, session):
        """Forgets episode by show ID and episode ID"""
        try:
            show = db.show_by_id(show_id, session=session)
        except NoResultFound:
            raise NotFoundError('show with ID %s not found' % show_id)
        try:
            episode = db.episode_by_id(ep_id, session)
        except NoResultFound:
            raise NotFoundError('episode with ID %s not found' % ep_id)
        if not db.episode_in_show(show_id, ep_id):
            raise BadRequest('episode with id %s does not belong to show %s' % (ep_id, show_id))

        args = delete_parser.parse_args()
        db.remove_series_entity(show.name, episode.identifier, args.get('forget'))

        return success_response('successfully removed episode %s from show %s' % (ep_id, show_id))


release_base_parser = api.parser()
release_base_parser.add_argument(
    'downloaded', type=inputs.boolean, help='Filter between release status'
)

sort_choices = ('first_seen', 'downloaded', 'proper_count', 'title')
release_list_parser = api.pagination_parser(release_base_parser, sort_choices)

release_delete_parser = release_base_parser.copy()
release_delete_parser.add_argument(
    'forget',
    type=inputs.boolean,
    default=False,
    help="Enabling this will for 'forget' event that will delete the downloaded"
    " releases from the entire DB, enabling to re-download them",
)


@api.response(NotFoundError)
@api.response(BadRequest)
@series_api.route('/<int:show_id>/seasons/<int:season_id>/releases/')
@api.doc(
    params={'show_id': 'ID of the show', 'season_id': 'Seasons ID'},
    description='Releases are any seen entries that match the seasons. \n'
    'The \'Series-ID\' header will be appended to the result headers.\n'
    'The \'Season-ID\' header will be appended to the result headers.',
)
class SeriesSeasonsReleasesAPI(APIResource):
    @etag
    @api.response(200, 'Releases retrieved successfully for season', season_release_list_schema)
    @api.doc(
        description='Get all matching releases for a specific season of a specific show.',
        parser=release_list_parser,
    )
    def get(self, show_id, season_id, session):
        """Get all season releases by show ID and season ID"""
        try:
            db.show_by_id(show_id, session=session)
        except NoResultFound:
            raise NotFoundError('show with ID %s not found' % show_id)
        try:
            season = db.season_by_id(season_id, session)
        except NoResultFound:
            raise NotFoundError('season with ID %s not found' % season_id)
        if not db.season_in_show(show_id, season_id):
            raise BadRequest(
                'seasons with id %s does not belong to show %s' % (season_id, show_id)
            )

        args = release_list_parser.parse_args()
        # Filter params
        downloaded = args.get('downloaded')

        # Pagination and sorting params
        page = args['page']
        per_page = args['per_page']
        sort_by = args['sort_by']
        sort_order = args['order']

        descending = sort_order == 'desc'

        # Handle max size limit
        if per_page > 100:
            per_page = 100

        start = per_page * (page - 1)
        stop = start + per_page

        kwargs = {
            'downloaded': downloaded,
            'start': start,
            'stop': stop,
            'sort_by': sort_by,
            'descending': descending,
            'season': season,
            'session': session,
        }

        # Total number of releases
        total_items = db.get_season_releases(count=True, **kwargs)

        # Release items
        release_items = [release.to_dict() for release in db.get_season_releases(**kwargs)]

        # Total number of pages
        total_pages = int(ceil(total_items / float(per_page)))

        if total_pages < page and total_pages != 0:
            raise NotFoundError('page %s does not exist' % page)

        # Actual results in page
        actual_size = min(per_page, len(release_items))

        # Get pagination headers
        pagination = pagination_headers(total_pages, total_items, actual_size, request)

        # Created response
        rsp = jsonify(release_items)

        # Add link header to response
        rsp.headers.extend(pagination)

        # Add Series-ID and Episode-ID headers
        rsp.headers.extend({'Series-ID': show_id, 'Season-ID': season_id})

        return rsp

    @api.response(200, 'Successfully deleted all releases for season', model=base_message_schema)
    @api.doc(
        description='Delete all releases for a specific season of a specific show.',
        parser=release_delete_parser,
    )
    def delete(self, show_id, season_id, session):
        """Deletes all season releases by show ID and season ID"""
        try:
            db.show_by_id(show_id, session=session)
        except NoResultFound:
            raise NotFoundError('show with ID %s not found' % show_id)
        try:
            season = db.season_by_id(season_id, session)
        except NoResultFound:
            raise NotFoundError('seasons with ID %s not found' % season_id)
        if not db.season_in_show(show_id, season_id):
            raise BadRequest('season with id %s does not belong to show %s' % (season_id, show_id))

        args = release_delete_parser.parse_args()
        downloaded = args.get('downloaded') is True if args.get('downloaded') is not None else None
        release_items = []
        for release in season.releases:
            if (
                downloaded
                and release.downloaded
                or downloaded is False
                and not release.downloaded
                or not downloaded
            ):
                release_items.append(release)

        for release in release_items:
            if args.get('forget'):
                fire_event('forget', release.title)
            db.delete_season_release_by_id(release.id)
        return success_response(
            'successfully deleted all releases for season %s from show %s' % (season_id, show_id)
        )

    @api.response(
        200, 'Successfully reset all downloaded releases for season', model=base_message_schema
    )
    @api.doc(
        description='Resets all of the downloaded releases of an season, clearing the quality to be downloaded '
        'again,'
    )
    def put(self, show_id, season_id, session):
        """Marks all downloaded season releases as not downloaded"""
        try:
            db.show_by_id(show_id, session=session)
        except NoResultFound:
            raise NotFoundError('show with ID %s not found' % show_id)
        try:
            season = db.season_by_id(season_id, session)
        except NoResultFound:
            raise NotFoundError('season with ID %s not found' % season_id)
        if not db.season_in_show(show_id, season_id):
            raise BadRequest('season with id %s does not belong to show %s' % (season_id, show_id))

        for release in season.releases:
            if release.downloaded:
                release.downloaded = False

        return success_response(
            'successfully reset download status for all releases for season %s from show %s'
            % (season_id, show_id)
        )


@api.response(NotFoundError)
@api.response(BadRequest)
@series_api.route('/<int:show_id>/seasons/<int:season_id>/releases/<int:rel_id>/')
@api.doc(
    params={'show_id': 'ID of the show', 'season_id': 'Season ID', 'rel_id': 'Release ID'},
    description='Releases are any seen entries that match the season. \n'
    'The \'Series-ID\' header will be appended to the result headers.\n'
    'The \'Season-ID\' header will be appended to the result headers.',
)
class SeriesSeasonReleaseAPI(APIResource):
    @etag
    @api.response(200, 'Release retrieved successfully for season', season_release_schema)
    @api.doc(
        description='Get a specific downloaded release for a specific season of a specific show'
    )
    def get(self, show_id, season_id, rel_id, session):
        """Get season release by show ID, season ID and release ID"""
        try:
            db.show_by_id(show_id, session=session)
        except NoResultFound:
            raise NotFoundError('show with ID %s not found' % show_id)
        try:
            db.season_by_id(season_id, session)
        except NoResultFound:
            raise NotFoundError('season with ID %s not found' % season_id)
        try:
            release = db.season_release_by_id(rel_id, session)
        except NoResultFound:
            raise NotFoundError('release with ID %s not found' % rel_id)
        if not db.season_in_show(show_id, season_id):
            raise BadRequest('season with id %s does not belong to show %s' % (season_id, show_id))
        if not db.release_in_season(season_id, rel_id):
            raise BadRequest('release id %s does not belong to season %s' % (rel_id, season_id))

        rsp = jsonify(release.to_dict())
        rsp.headers.extend({'Series-ID': show_id, 'Season-ID': season_id})
        return rsp

    @api.response(200, 'Release successfully deleted', model=base_message_schema)
    @api.doc(
        description='Delete a specific releases for a specific season of a specific show.',
        parser=delete_parser,
    )
    def delete(self, show_id, season_id, rel_id, session):
        """Delete episode release by show ID, season ID and release ID"""
        try:
            db.show_by_id(show_id, session=session)
        except NoResultFound:
            raise NotFoundError('show with ID %s not found' % show_id)
        try:
            db.season_by_id(season_id, session)
        except NoResultFound:
            raise NotFoundError('season with ID %s not found' % season_id)
        try:
            release = db.season_release_by_id(rel_id, session)
        except NoResultFound:
            raise NotFoundError('release with ID %s not found' % rel_id)
        if not db.season_in_show(show_id, season_id):
            raise BadRequest('season with id %s does not belong to show %s' % (season_id, show_id))
        if not db.release_in_season(season_id, rel_id):
            raise BadRequest('release id %s does not belong to season %s' % (rel_id, season_id))
        args = delete_parser.parse_args()
        if args.get('forget'):
            fire_event('forget', release.title)

        db.delete_season_release_by_id(rel_id)
        return success_response(
            'successfully deleted release %d from season %d' % (rel_id, season_id)
        )

    @api.response(200, 'Successfully reset downloaded release status', model=season_release_schema)
    @api.doc(
        description='Resets the downloaded release status, clearing the quality to be downloaded again'
    )
    def put(self, show_id, season_id, rel_id, session):
        """Resets a downloaded release status"""
        try:
            db.show_by_id(show_id, session=session)
        except NoResultFound:
            raise NotFoundError('show with ID %s not found' % show_id)
        try:
            db.season_by_id(season_id, session)
        except NoResultFound:
            raise NotFoundError('season with ID %s not found' % season_id)
        try:
            release = db.season_release_by_id(rel_id, session)
        except NoResultFound:
            raise NotFoundError('release with ID %s not found' % rel_id)
        if not db.season_in_show(show_id, season_id):
            raise BadRequest('season with id %s does not belong to show %s' % (season_id, show_id))
        if not db.release_in_season(season_id, rel_id):
            raise BadRequest('release id %s does not belong to episode %s' % (rel_id, season_id))

        if not release.downloaded:
            raise BadRequest('release with id %s is not set as downloaded' % rel_id)
        release.downloaded = False

        rsp = jsonify(release.to_dict())
        rsp.headers.extend({'Series-ID': show_id, 'Season-ID': season_id})
        return rsp


@api.response(NotFoundError)
@api.response(BadRequest)
@series_api.route('/<int:show_id>/episodes/<int:ep_id>/releases/')
@api.doc(
    params={'show_id': 'ID of the show', 'ep_id': 'Episode ID'},
    description='Releases are any seen entries that match the episode. \n'
    'The \'Series-ID\' header will be appended to the result headers.\n'
    'The \'Episode-ID\' header will be appended to the result headers.',
)
class SeriesEpisodeReleasesAPI(APIResource):
    @etag
    @api.response(200, 'Releases retrieved successfully for episode', episode_release_list_schema)
    @api.doc(
        description='Get all matching releases for a specific episode of a specific show.',
        parser=release_list_parser,
    )
    def get(self, show_id, ep_id, session):
        """Get all episodes releases by show ID and episode ID"""
        try:
            db.show_by_id(show_id, session=session)
        except NoResultFound:
            raise NotFoundError('show with ID %s not found' % show_id)
        try:
            episode = db.episode_by_id(ep_id, session)
        except NoResultFound:
            raise NotFoundError('episode with ID %s not found' % ep_id)
        if not db.episode_in_show(show_id, ep_id):
            raise BadRequest('episode with id %s does not belong to show %s' % (ep_id, show_id))

        args = release_list_parser.parse_args()
        # Filter params
        downloaded = args.get('downloaded')

        # Pagination and sorting params
        page = args['page']
        per_page = args['per_page']
        sort_by = args['sort_by']
        sort_order = args['order']

        descending = sort_order == 'desc'

        # Handle max size limit
        if per_page > 100:
            per_page = 100

        start = per_page * (page - 1)
        stop = start + per_page

        kwargs = {
            'downloaded': downloaded,
            'start': start,
            'stop': stop,
            'sort_by': sort_by,
            'descending': descending,
            'episode': episode,
            'session': session,
        }

        # Total number of releases
        total_items = db.get_episode_releases(count=True, **kwargs)

        # Release items
        release_items = [release.to_dict() for release in db.get_episode_releases(**kwargs)]

        # Total number of pages
        total_pages = int(ceil(total_items / float(per_page)))

        if total_pages < page and total_pages != 0:
            raise NotFoundError('page %s does not exist' % page)

        # Actual results in page
        actual_size = min(per_page, len(release_items))

        # Get pagination headers
        pagination = pagination_headers(total_pages, total_items, actual_size, request)

        # Created response
        rsp = jsonify(release_items)

        # Add link header to response
        rsp.headers.extend(pagination)

        # Add Series-ID and Episode-ID headers
        rsp.headers.extend({'Series-ID': show_id, 'Episode-ID': ep_id})

        return rsp

    @api.response(200, 'Successfully deleted all releases for episode', model=base_message_schema)
    @api.doc(
        description='Delete all releases for a specific episode of a specific show.',
        parser=release_delete_parser,
    )
    def delete(self, show_id, ep_id, session):
        """Deletes all episodes releases by show ID and episode ID"""
        try:
            db.show_by_id(show_id, session=session)
        except NoResultFound:
            raise NotFoundError('show with ID %s not found' % show_id)
        try:
            episode = db.episode_by_id(ep_id, session)
        except NoResultFound:
            raise NotFoundError('episode with ID %s not found' % ep_id)
        if not db.episode_in_show(show_id, ep_id):
            raise BadRequest('episode with id %s does not belong to show %s' % (ep_id, show_id))

        args = release_delete_parser.parse_args()
        downloaded = args.get('downloaded') is True if args.get('downloaded') is not None else None
        release_items = []
        for release in episode.releases:
            if (
                downloaded
                and release.downloaded
                or downloaded is False
                and not release.downloaded
                or not downloaded
            ):
                release_items.append(release)

        for release in release_items:
            if args.get('forget'):
                fire_event('forget', release.title)
            db.delete_episode_release_by_id(release.id)
        return success_response(
            'successfully deleted all releases for episode %s from show %s' % (ep_id, show_id)
        )

    @api.response(
        200, 'Successfully reset all downloaded releases for episode', model=base_message_schema
    )
    @api.doc(
        description='Resets all of the downloaded releases of an episode, clearing the quality to be downloaded '
        'again,'
    )
    def put(self, show_id, ep_id, session):
        """Marks all downloaded releases as not downloaded"""
        try:
            db.show_by_id(show_id, session=session)
        except NoResultFound:
            raise NotFoundError('show with ID %s not found' % show_id)
        try:
            episode = db.episode_by_id(ep_id, session)
        except NoResultFound:
            raise NotFoundError('episode with ID %s not found' % ep_id)
        if not db.episode_in_show(show_id, ep_id):
            raise BadRequest('episode with id %s does not belong to show %s' % (ep_id, show_id))

        for release in episode.releases:
            if release.downloaded:
                release.downloaded = False

        return success_response(
            'successfully reset download status for all releases for episode %s from show %s'
            % (ep_id, show_id)
        )


@api.response(NotFoundError)
@api.response(BadRequest)
@series_api.route('/<int:show_id>/episodes/<int:ep_id>/releases/<int:rel_id>/')
@api.doc(
    params={'show_id': 'ID of the show', 'ep_id': 'Episode ID', 'rel_id': 'Release ID'},
    description='Releases are any seen entries that match the episode. \n'
    'The \'Series-ID\' header will be appended to the result headers.\n'
    'The \'Episode-ID\' header will be appended to the result headers.',
)
class SeriesEpisodeReleaseAPI(APIResource):
    @etag
    @api.response(200, 'Release retrieved successfully for episode', episode_release_schema)
    @api.doc(
        description='Get a specific downloaded release for a specific episode of a specific show'
    )
    def get(self, show_id, ep_id, rel_id, session):
        """Get episode release by show ID, episode ID and release ID"""
        try:
            db.show_by_id(show_id, session=session)
        except NoResultFound:
            raise NotFoundError('show with ID %s not found' % show_id)
        try:
            db.episode_by_id(ep_id, session)
        except NoResultFound:
            raise NotFoundError('episode with ID %s not found' % ep_id)
        try:
            release = db.episode_release_by_id(rel_id, session)
        except NoResultFound:
            raise NotFoundError('release with ID %s not found' % rel_id)
        if not db.episode_in_show(show_id, ep_id):
            raise BadRequest('episode with id %s does not belong to show %s' % (ep_id, show_id))
        if not db.release_in_episode(ep_id, rel_id):
            raise BadRequest('release id %s does not belong to episode %s' % (rel_id, ep_id))

        rsp = jsonify(release.to_dict())
        rsp.headers.extend({'Series-ID': show_id, 'Episode-ID': ep_id})
        return rsp

    @api.response(200, 'Release successfully deleted', model=base_message_schema)
    @api.doc(
        description='Delete a specific releases for a specific episode of a specific show.',
        parser=delete_parser,
    )
    def delete(self, show_id, ep_id, rel_id, session):
        """Delete episode release by show ID, episode ID and release ID"""
        try:
            db.show_by_id(show_id, session=session)
        except NoResultFound:
            raise NotFoundError('show with ID %s not found' % show_id)
        try:
            db.episode_by_id(ep_id, session)
        except NoResultFound:
            raise NotFoundError('episode with ID %s not found' % ep_id)
        try:
            release = db.episode_release_by_id(rel_id, session)
        except NoResultFound:
            raise NotFoundError('release with ID %s not found' % rel_id)
        if not db.episode_in_show(show_id, ep_id):
            raise BadRequest('episode with id %s does not belong to show %s' % (ep_id, show_id))
        if not db.release_in_episode(ep_id, rel_id):
            raise BadRequest('release id %s does not belong to episode %s' % (rel_id, ep_id))
        args = delete_parser.parse_args()
        if args.get('forget'):
            fire_event('forget', release.title)

        db.delete_episode_release_by_id(rel_id)
        return success_response(
            'successfully deleted release %d from episode %d' % (rel_id, ep_id)
        )

    @api.response(
        200, 'Successfully reset downloaded release status', model=episode_release_schema
    )
    @api.doc(
        description='Resets the downloaded release status, clearing the quality to be downloaded again'
    )
    def put(self, show_id, ep_id, rel_id, session):
        """Resets a downloaded release status"""
        try:
            db.show_by_id(show_id, session=session)
        except NoResultFound:
            raise NotFoundError('show with ID %s not found' % show_id)
        try:
            db.episode_by_id(ep_id, session)
        except NoResultFound:
            raise NotFoundError('episode with ID %s not found' % ep_id)
        try:
            release = db.episode_release_by_id(rel_id, session)
        except NoResultFound:
            raise NotFoundError('release with ID %s not found' % rel_id)
        if not db.episode_in_show(show_id, ep_id):
            raise BadRequest('episode with id %s does not belong to show %s' % (ep_id, show_id))
        if not db.release_in_episode(ep_id, rel_id):
            raise BadRequest('release id %s does not belong to episode %s' % (rel_id, ep_id))

        if not release.downloaded:
            raise BadRequest('release with id %s is not set as downloaded' % rel_id)
        release.downloaded = False

        rsp = jsonify(release.to_dict())
        rsp.headers.extend({'Series-ID': show_id, 'Episode-ID': ep_id})
        return rsp
