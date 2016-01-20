from __future__ import unicode_literals, division, absolute_import

import logging
from math import ceil
from operator import itemgetter

from flask import jsonify, request
from flask_restful import inputs
from sqlalchemy import Column, Integer, String, ForeignKey, or_, and_, select, update, func
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from flexget import db_schema, plugin
from flexget.api import api, APIResource
from flexget.entry import Entry
from flexget.event import event
from flexget.manager import Session
from flexget.utils import qualities
from flexget.utils.database import quality_requirement_property, with_session
from flexget.utils.imdb import extract_id
from flexget.utils.log import log_once
from flexget.utils.sqlalchemy_utils import table_exists, table_schema

try:
    from flexget.plugins.filter import queue_base
except ImportError:
    raise plugin.DependencyError(issued_by='movie_queue', missing='queue_base',
                                 message='movie_queue requires the queue_base plugin')

log = logging.getLogger('movie_queue')
Base = db_schema.versioned_base('movie_queue', 3)


@event('manager.lock_acquired')
def migrate_imdb_queue(manager):
    """If imdb_queue table is found, migrate the data to movie_queue"""
    session = Session()
    try:
        if table_exists('imdb_queue', session):
            log.info('Migrating imdb_queue items to movie_queue')
            old_table = table_schema('imdb_queue', session)
            for row in session.execute(old_table.select()):
                try:
                    queue_add(imdb_id=row['imdb_id'], quality=row['quality'], session=session)
                except QueueError as e:
                    log.error('Unable to migrate %s from imdb_queue to movie_queue' % row['title'])
            old_table.drop()
            session.commit()
    finally:
        session.close()


@db_schema.upgrade('movie_queue')
def upgrade(ver, session):
    if ver == 0:
        # Translate old qualities into new quality requirements
        movie_table = table_schema('movie_queue', session)
        for row in session.execute(select([movie_table.c.id, movie_table.c.quality])):
            # Webdl quality no longer has dash
            new_qual = row['quality'].replace('web-dl', 'webdl')
            if new_qual.lower() != 'any':
                # Old behavior was to get specified quality or greater, approximate that with new system
                new_qual = ' '.join(qual + '+' for qual in new_qual.split(' '))
            session.execute(update(movie_table, movie_table.c.id == row['id'],
                                   {'quality': new_qual}))
        ver = 1
    if ver == 1:
        # Bad upgrade left some qualities as 'ANY+'
        movie_table = table_schema('movie_queue', session)
        for row in session.execute(select([movie_table.c.id, movie_table.c.quality])):
            if row['quality'].lower() == 'any+':
                session.execute(update(movie_table, movie_table.c.id == row['id'],
                                       {'quality': 'ANY'}))
        ver = 2
    if ver == 2:
        from flexget.utils.imdb import ImdbParser
        # Corrupted movie titles may be in the queue due to imdb layout changes. GitHub #729
        movie_table = table_schema('movie_queue', session)
        queue_base_table = table_schema('queue', session)
        query = select([movie_table.c.id, movie_table.c.imdb_id, queue_base_table.c.title])
        query = query.where(movie_table.c.id == queue_base_table.c.id)
        for row in session.execute(query):
            if row['imdb_id'] and (not row['title'] or row['title'] == 'None' or '\n' in row['title']):
                log.info('Fixing movie_queue title for %s' % row['imdb_id'])
                parser = ImdbParser()
                parser.parse(row['imdb_id'])
                if parser.name:
                    session.execute(update(queue_base_table, queue_base_table.c.id == row['id'],
                                           {'title': parser.name}))
        ver = 3
    return ver


class QueuedMovie(queue_base.QueuedItem, Base):
    __tablename__ = 'movie_queue'
    __mapper_args__ = {'polymorphic_identity': 'movie'}
    id = Column(Integer, ForeignKey('queue.id'), primary_key=True)
    imdb_id = Column(String)
    tmdb_id = Column(Integer)
    quality = Column('quality', String)
    quality_req = quality_requirement_property('quality')

    def to_dict(self):
        return {
            'added': self.added,
            'downloaded': self.downloaded,
            'entry_original_url': self.entry_original_url,
            'entry_title': self.entry_title,
            'entry_url': self.entry_url,
            'id': self.id,
            'imdb_id': self.imdb_id,
            'tmdb_id': self.tmdb_id,
            'quality': self.quality,
            'quality_req': self.quality_req.text,
            'title': self.title,
        }


class MovieQueue(queue_base.FilterQueueBase):
    schema = {
        'oneOf': [
            {'type': 'string', 'enum': ['accept', 'add', 'remove', 'forget']},
            {
                'type': 'object',
                'properties': {
                    'action': {'type': 'string', 'enum': ['accept', 'add', 'remove', 'forget']},
                    'quality': {'type': 'string', 'format': 'quality_requirements'},
                },
                'required': ['action'],
                'additionalProperties': False
            }
        ]
    }

    def matches(self, task, config, entry):
        if not config:
            return
        if not isinstance(config, dict):
            config = {'action': config}
        # only the accept action is applied in the 'matches' section
        if config.get('action') != 'accept':
            return

        # Tell tmdb_lookup to add lazy lookup fields if not already present
        try:
            plugin.get_plugin_by_name('imdb_lookup').instance.register_lazy_fields(entry)
        except plugin.DependencyError:
            log.debug('imdb_lookup is not available, queue will not work if movie ids are not populated')
        try:
            plugin.get_plugin_by_name('tmdb_lookup').instance.lookup(entry)
        except plugin.DependencyError:
            log.debug('tmdb_lookup is not available, queue will not work if movie ids are not populated')

        conditions = []
        # Check if a movie id is already populated before incurring a lazy lookup
        for lazy in [False, True]:
            if entry.get('imdb_id', eval_lazy=lazy):
                conditions.append(QueuedMovie.imdb_id == entry['imdb_id'])
            if entry.get('tmdb_id', eval_lazy=lazy and not conditions):
                conditions.append(QueuedMovie.tmdb_id == entry['tmdb_id'])
            if conditions:
                break
        if not conditions:
            log_once('IMDB and TMDB lookups failed for %s.' % entry['title'], log, logging.WARN)
            return

        quality = entry.get('quality', qualities.Quality())

        movie = task.session.query(QueuedMovie).filter(QueuedMovie.downloaded == None). \
            filter(or_(*conditions)).first()
        if movie and movie.quality_req.allows(quality):
            return movie

    def on_task_output(self, task, config):
        if not config:
            return
        if not isinstance(config, dict):
            config = {'action': config}
        for entry in task.accepted:
            # Tell tmdb_lookup to add lazy lookup fields if not already present
            try:
                plugin.get_plugin_by_name('tmdb_lookup').instance.lookup(entry)
            except plugin.DependencyError:
                log.debug('tmdb_lookup is not available, queue will not work if movie ids are not populated')
            # Find one or both movie id's for this entry. See if an id is already populated before incurring lazy lookup
            kwargs = {}
            for lazy in [False, True]:
                if entry.get('imdb_id', eval_lazy=lazy):
                    kwargs['imdb_id'] = entry['imdb_id']
                if entry.get('tmdb_id', eval_lazy=lazy):
                    kwargs['tmdb_id'] = entry['tmdb_id']
                if kwargs:
                    break
            if not kwargs:
                log.warning('Could not determine a movie id for %s, it will not be added to queue.' % entry['title'])
                continue

            # Provide movie title if it is already available, to avoid movie_queue doing a lookup
            kwargs['title'] = (entry.get('imdb_name', eval_lazy=False) or
                               entry.get('tmdb_name', eval_lazy=False) or
                               entry.get('movie_name', eval_lazy=False))
            log.debug('movie_queue kwargs: %s' % kwargs)
            try:
                action = config.get('action')
                if action == 'add':
                    # since entries usually have unknown quality we need to ignore that ..
                    if entry.get('quality_req'):
                        kwargs['quality'] = qualities.Requirements(entry['quality_req'])
                    elif entry.get('quality'):
                        kwargs['quality'] = qualities.Requirements(entry['quality'].name)
                    else:
                        kwargs['quality'] = qualities.Requirements(config.get('quality', 'any'))
                    queue_add(**kwargs)
                elif action == 'remove':
                    queue_del(**kwargs)
                elif action == 'forget':
                    queue_forget(**kwargs)
            except QueueError as e:
                # Ignore already in queue errors
                if e.errno != 1:
                    entry.fail('Error adding movie to queue: %s' % e.message)


class QueueError(Exception):
    """Exception raised if there is an error with a queue operation"""

    # TODO: I think message was removed from exception baseclass and is now masked
    # some other custom exception (DependencyError) had to make so tweaks to make it work ..

    def __init__(self, message, errno=0):
        self.message = message
        self.errno = errno


@with_session
def parse_what(what, lookup=True, session=None):
    """
    Determines what information was provided by the search string `what`.
    If `lookup` is true, will fill in other information from tmdb.

    :param what: Can be one of:
      <Movie Title>: Search based on title
      imdb_id=<IMDB id>: search based on imdb id
      tmdb_id=<TMDB id>: search based on tmdb id
    :param bool lookup: Whether missing info should be filled in from tmdb.
    :param session: An existing session that will be used for lookups if provided.
    :rtype: dict
    :return: A dictionary with 'title', 'imdb_id' and 'tmdb_id' keys
    """

    tmdb_lookup = plugin.get_plugin_by_name('api_tmdb').instance.lookup

    result = {'title': None, 'imdb_id': None, 'tmdb_id': None}
    result['imdb_id'] = extract_id(what)
    if not result['imdb_id']:
        if isinstance(what, int):
            result['tmdb_id'] = what
        elif what.startswith('tmdb_id='):
            result['tmdb_id'] = what[8:]
        else:
            result['title'] = what

    if not lookup:
        # If not doing an online lookup we can return here
        return result

    search_entry = Entry(title=result['title'] or '')
    for field in ['imdb_id', 'tmdb_id']:
        if result.get(field):
            search_entry[field] = result[field]
    # Put lazy lookup fields on the search entry
    plugin.get_plugin_by_name('imdb_lookup').instance.register_lazy_fields(search_entry)
    plugin.get_plugin_by_name('tmdb_lookup').instance.lookup(search_entry)

    try:
        # Both ids are optional, but if movie_name was populated at least one of them will be there
        return {'title': search_entry['movie_name'], 'imdb_id': search_entry.get('imdb_id'),
                'tmdb_id': search_entry.get('tmdb_id')}
    except KeyError as e:
        raise QueueError(e.message)


# API functions to edit queue
@with_session
def queue_add(title=None, imdb_id=None, tmdb_id=None, quality=None, session=None):
    """
    Add an item to the queue with the specified quality requirements.

    One or more of `title` `imdb_id` or `tmdb_id` must be specified when calling this function.

    :param title: Title of the movie. (optional)
    :param imdb_id: IMDB id for the movie. (optional)
    :param tmdb_id: TMDB id for the movie. (optional)
    :param quality: A QualityRequirements object defining acceptable qualities.
    :param session: Optional session to use for database updates
    """

    quality = quality or qualities.Requirements('any')

    if not title or not (imdb_id or tmdb_id):
        # We don't have all the info we need to add movie, do a lookup for more info
        result = parse_what(imdb_id or title or tmdb_id, session=session)
        title = result['title']
        if not title:
            raise QueueError('Could not parse movie info for given parameters: title=%s, imdb_id=%s, tmdb_id=%s' % (
                title, imdb_id, tmdb_id))
        imdb_id = result['imdb_id']
        tmdb_id = result['tmdb_id']

    # check if the item is already queued
    item = session.query(QueuedMovie).filter(or_(and_(QueuedMovie.imdb_id != None, QueuedMovie.imdb_id == imdb_id),
                                                 and_(QueuedMovie.tmdb_id != None, QueuedMovie.tmdb_id == tmdb_id))). \
        first()
    if not item:
        item = QueuedMovie(title=title, imdb_id=imdb_id, tmdb_id=tmdb_id, quality=quality.text)
        session.add(item)
        session.commit()
        log.info('Adding %s to movie queue with quality=%s.' % (title, quality))
        return item.to_dict()
    else:
        if item.downloaded:
            raise QueueError('ERROR: %s has already been queued and downloaded' % title, errno=1)
        else:
            raise QueueError('ERROR: %s is already in the queue' % title, errno=1)


@with_session
def queue_del(title=None, imdb_id=None, tmdb_id=None, session=None, movie_id=None):
    """
    Delete the given item from the queue.

    :param title: Movie title
    :param imdb_id: Imdb id
    :param tmdb_id: Tmdb id
    :param session: Optional session to use, new session used otherwise
    :return: Title of forgotten movie
    :raises QueueError: If queued item could not be found with given arguments
    """
    log.debug('queue_del - title=%s, imdb_id=%s, tmdb_id=%s, movie_id=%s', title, imdb_id, tmdb_id, movie_id)
    query = session.query(QueuedMovie)
    if imdb_id:
        query = query.filter(QueuedMovie.imdb_id == imdb_id)
    elif tmdb_id:
        query = query.filter(QueuedMovie.tmdb_id == tmdb_id)
    elif title:
        query = query.filter(func.lower(QueuedMovie.title) == func.lower(title))
    elif movie_id:
        query = query.filter(QueuedMovie.id == movie_id)
    try:
        item = query.one()
        title = item.title
        session.delete(item)
        return title
    except NoResultFound as e:
        raise QueueError(
                'title=%s, imdb_id=%s, tmdb_id=%s, movie_id=%s not found in queue' % (
                    title, imdb_id, tmdb_id, movie_id))
    except MultipleResultsFound:
        raise QueueError('title=%s, imdb_id=%s, tmdb_id=%s, movie_id=%s matches multiple results in queue' %
                         (title, imdb_id, tmdb_id, movie_id))


@with_session
def queue_forget(title=None, imdb_id=None, tmdb_id=None, session=None, movie_id=None):
    """
    Forget movie download  from the queue.

    :param title: Movie title
    :param imdb_id: Imdb id
    :param tmdb_id: Tmdb id
    :param session: Optional session to use, new session used otherwise
    :return: Title of forgotten movie
    :raises QueueError: If queued item could not be found with given arguments
    """
    log.debug('queue_forget - title=%s, imdb_id=%s, tmdb_id=%s, movie_id=%s', title, imdb_id, tmdb_id, movie_id)
    query = session.query(QueuedMovie)
    if imdb_id:
        query = query.filter(QueuedMovie.imdb_id == imdb_id)
    elif tmdb_id:
        query = query.filter(QueuedMovie.tmdb_id == tmdb_id)
    elif title:
        query = query.filter(QueuedMovie.title == title)
    elif movie_id:
        query = query.filter(QueuedMovie.id == movie_id)
    try:
        item = query.one()
        title = item.title
        if not item.downloaded:
            raise QueueError('%s is not marked as downloaded' % title)
        item.downloaded = None
        return item.to_dict()
    except NoResultFound as e:
        raise QueueError('title=%s, imdb_id=%s, tmdb_id=%s, movie_id=%s not found in queue' %
                         (title, imdb_id, tmdb_id, movie_id))


@with_session
def queue_edit(quality, imdb_id=None, tmdb_id=None, session=None, movie_id=None):
    """
    :param quality: Change the required quality for a movie in the queue
    :param imdb_id: Imdb id
    :param tmdb_id: Tmdb id
    :param session: Optional session to use, new session used otherwise
    :return: Title of edited item
    :raises QueueError: If queued item could not be found with given arguments
    """
    # check if the item is queued
    log.debug('queue_edit - quality=%s, imdb_id=%s, tmdb_id=%s, movie_id=%s', quality, imdb_id, tmdb_id, movie_id)
    query = session.query(QueuedMovie)
    if imdb_id:
        query = session.query(QueuedMovie).filter(QueuedMovie.imdb_id == imdb_id)
    elif tmdb_id:
        query = session.query(QueuedMovie).filter(QueuedMovie.tmdb_id == tmdb_id)
    elif movie_id:
        query = session.query(QueuedMovie).filter(QueuedMovie.id == movie_id)
    try:
        item = query.one()
        item.quality = quality
        return item.to_dict()
    except NoResultFound as e:
        raise QueueError('imdb_id=%s, tmdb_id=%s, movie_id=%s not found in queue' % (imdb_id, tmdb_id, movie_id))


@with_session
def queue_get(session=None, downloaded=None):
    """
    Get the current movie queue.

    :param session: New session is used it not given
    :param bool downloaded: Whether or not to return only downloaded
    :return: List of QueuedMovie objects (detached from session)
    """
    query = session.query(QueuedMovie)
    if downloaded is False:
        return query.filter(QueuedMovie.downloaded == None).all()
    elif downloaded:
        return query.filter(QueuedMovie.downloaded != None).all()
    else:
        return query.all()


@event('plugin.register')
def register_plugin():
    plugin.register(MovieQueue, 'movie_queue', api_ver=2)


movie_queue_api = api.namespace('movie_queue', description='Movie Queue operations')

movie_object = {
    'type': 'object',
    'properties': {
        'added': {'type': 'string'},
        'downloaded': {'type': 'string'},
        'entry_original_url': {'type': 'string'},
        'entry_title': {'type': 'string'},
        'entry_url': {'type': 'string'},
        'id': {'type': 'integer'},
        'imdb_id': {'type': 'string'},
        'quality': {'type': 'string'},
        'title': {'type': 'string'},
        'tmdb_id': {'type': 'string'},
    }
}

movie_queue_schema = {
    'type': 'object',
    'properties': {
        'movies': {
            'type': 'array',
            'items': movie_object
        },
        'number_of_movies': {'type': 'integer'},
        'total_number_of_pages': {'type': 'integer'},
        'page_number': {'type': 'integer'}

    }
}
movie_queue_status_value_enum_list = ['pending', 'downloaded', 'all']


def movie_queue_status_value_enum(value):
    """ Movie queue status enum. Return True for 'downloaded', False for 'pending' and None for 'all' """
    enum = movie_queue_status_value_enum_list
    if isinstance(value, bool):
        return value
    if value not in enum:
        raise ValueError('Value expected to be in' + ' ,'.join(enum))
    if value == 'downloaded':
        return True
    elif value == 'pending':
        return False
    else:
        return None


def movie_queue_sort_value_enum(value):
    enum = ['added', 'downloaded', 'id', 'title']
    if value not in enum:
        raise ValueError('Value expected to be in' + ' ,'.join(enum))
    return value


def movie_queue_sort_order_enum(value):
    enum = ['desc', 'asc']
    if isinstance(value, bool):
        return value
    if value not in enum:
        raise ValueError('Value expected to be in' + ' ,'.join(enum))
    if value == 'desc':
        return True
    return False


movie_queue_schema = api.schema('list_movie_queue', movie_queue_schema)

movie_queue_parser = api.parser()
movie_queue_parser.add_argument('page', type=int, default=1, help='Page number')
movie_queue_parser.add_argument('max', type=int, default=100, help='Movies per page')
movie_queue_parser.add_argument('status', type=movie_queue_status_value_enum, default=False,
                                help='Filter list by status. Filter by {0}. Default is "pending"'.format(
                                    ' ,'.join(movie_queue_status_value_enum_list)))
movie_queue_parser.add_argument('sort_by', type=movie_queue_sort_value_enum, default='added',
                                help="Sort response by 'added', 'downloaded', 'id', 'title'")
movie_queue_parser.add_argument('order', type=movie_queue_sort_order_enum, default='desc', help='Sorting order')

movie_add_results_schema = {
    'type': 'object',
    'properties': {
        'message': {'type': 'string'},
        'movie': movie_object
    }
}

movie_add_input_schema = {
    'type': 'object',
    'properties': {
        'title': {'type': 'string'},
        'imdb_id': {'type': 'string', 'pattern': r'tt\d{7}'},
        'tmdb_id': {'type': 'integer'},
        'quality': {'type': 'string', 'format': 'quality_requirements', 'default': 'any'}
    },
    'anyOf': [
        {'required': ['title']},
        {'required': ['imdb_id']},
        {'required': ['tmdb_id']}
    ]
}

movie_add_results_schema = api.schema('movie_add_results', movie_add_results_schema)
movie_add_input_schema = api.schema('movie_add_input_schema', movie_add_input_schema)

movie_edit_results_schema = {
    'type': 'object',
    'properties': {
        'message': {'type': 'string'},
        'movie': movie_object
    }
}

movie_edit_input_schema = {
    'type': 'object',
    'properties': {
        'quality': {'type': 'string', 'format': 'quality_requirements'},
        'reset_downloaded': {'type': 'boolean', 'default': False}
    },
    'anyOf': [
        {'required': ['quality']},
        {'required': ['reset_downloaded']}
    ]
}

movie_edit_results_schema = api.schema('movie_edit_results_schema', movie_edit_results_schema)
movie_edit_input_schema = api.schema('movie_edit_input_schema', movie_edit_input_schema)


@movie_queue_api.route('/')
class MovieQueueAPI(APIResource):
    @api.response(404, 'Page does not exist')
    @api.response(200, 'Movie queue retrieved successfully', movie_queue_schema)
    @api.doc(parser=movie_queue_parser)
    def get(self, session=None):
        """ List queued movies """
        args = movie_queue_parser.parse_args()
        page = args['page']
        max_results = args['max']
        downloaded = args['status']
        sort_by = args['sort_by']
        order = args['order']
        # Handles default if it explicitly called
        if order == 'desc':
            order = True

        movie_queue = queue_get(session=session, downloaded=downloaded)
        count = len(movie_queue)

        pages = int(ceil(count / float(max_results)))

        movie_items = []

        if page > pages and pages != 0:
            return {'error': 'page %s does not exist' % page}, 404

        start = (page - 1) * max_results
        finish = start + max_results
        if finish > count:
            finish = count

        for movie_number in range(start, finish):
            movie_items.append(movie_queue[movie_number].to_dict())

        sorted_movie_list = sorted(movie_items, key=itemgetter(sort_by), reverse=order)

        return jsonify({
            'movies': sorted_movie_list,
            'number_of_movies': count,
            'page_number': page,
            'total_number_of_pages': pages
        })

    @api.response(400, 'Page not found')
    @api.response(201, 'Movie successfully added', movie_add_results_schema)
    @api.validate(movie_add_input_schema)
    def post(self, session=None):
        """ Add movies to movie queue """
        kwargs = request.json
        kwargs['quality'] = qualities.Requirements(kwargs.get('quality'))
        kwargs['session'] = session

        try:
            movie = queue_add(**kwargs)
        except QueueError as e:
            reply = {
                'status': 'error',
                'message': e.message
            }
            return reply, 404

        reply = jsonify(
                {
                    'message': 'Successfully added movie to movie queue',
                    'movie': movie
                }
        )
        reply.status_code = 201
        return reply


@api.response(404, 'Movie not found')
@api.response(400, 'Invalid type received')
@movie_queue_api.route('/<type>/<id>/')
@api.doc(params={'id': 'ID of Queued Movie', 'type': 'Type of ID to be used (imdb/tmdb/movie_id)'})
class MovieQueueManageAPI(APIResource):
    def validate_type(self, type, id, session):
        if type not in ['imdb', 'tmdb', 'movie_id']:
            reply = {
                'status': 'error',
                'message': 'invalid ID type received. Must be one of (imdb/tmdb/movie_id)'
            }
            return reply, 400
        kwargs = {'session': session}
        if type == 'imdb':
            kwargs['imdb_id'] = id
        elif type == 'tmdb':
            kwargs['tmdb_id'] = id
        elif type == 'movie_id':
            kwargs['movie_id'] = id
        return kwargs

    @api.response(200, 'Movie successfully deleted')
    def delete(self, type, id, session=None):
        """ Delete movies from movie queue """
        kwargs = self.validate_type(type, id, session)
        try:
            queue_del(**kwargs)
        except QueueError as e:
            reply = {'status': 'error',
                     'message': e.message}
            return reply, 404

        reply = jsonify(
                {'status': 'success',
                 'message': 'successfully deleted {0} movie {1}'.format(type, id)})
        return reply

    @api.response(200, 'Movie successfully updated', movie_edit_results_schema)
    @api.validate(movie_edit_input_schema)
    def put(self, type, id, session=None):
        """ Updates movie quality or downloaded state in movie queue """
        kwargs = self.validate_type(type, id, session)
        movie = None
        data = request.json
        if data.get('reset_downloaded'):
            try:
                movie = queue_forget(**kwargs)
            except QueueError as e:
                reply = {
                    'status': 'error',
                    'message': e.message
                }
                return reply, 404

        if data.get('quality'):
            kwargs['quality'] = data['quality']
            try:
                movie = queue_edit(**kwargs)
            except QueueError as e:
                reply = {'status': 'error',
                         'message': e.message}
                return reply, 404
        if not movie:
            return {'status': 'error',
                    'message': 'Not enough parameters to edit movie data'}, 400

        return jsonify(
                {
                    'status': 'success',
                    'message': 'Successfully updated movie details',
                    'movie': movie
                }
        )
