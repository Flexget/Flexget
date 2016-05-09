from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from sqlalchemy import Column, Integer, String, ForeignKey, or_, and_, select, update, func, Unicode
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from flexget import db_schema, plugin
from flexget.entry import Entry
from flexget.event import event
from flexget.manager import Session
from flexget.utils import qualities
from flexget.utils.database import quality_requirement_property, with_session
from flexget.utils.imdb import extract_id
from flexget.utils.log import log_once
from flexget.utils.sqlalchemy_utils import table_exists, table_schema, table_add_column

try:
    from flexget.plugins.filter import queue_base
except ImportError:
    raise plugin.DependencyError(issued_by='movie_queue', missing='queue_base',
                                 message='movie_queue requires the queue_base plugin')

log = logging.getLogger('movie_queue')
Base = db_schema.versioned_base('movie_queue', 4)


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
    if ver == 3:
        # adding queue_name column to movie_queue table and setting initial value to default)
        table_add_column('movie_queue', 'queue_name', Unicode, session, default='default')
        ver = 4
    return ver


class QueuedMovie(queue_base.QueuedItem, Base):
    __tablename__ = 'movie_queue'
    __mapper_args__ = {'polymorphic_identity': 'movie'}
    id = Column(Integer, ForeignKey('queue.id'), primary_key=True)
    imdb_id = Column(String)
    tmdb_id = Column(Integer)
    quality = Column('quality', String)
    quality_req = quality_requirement_property('quality')
    queue_name = Column(Unicode)

    def to_dict(self):
        return {
            'added': self.added,
            'is_downloaded': True if self.downloaded else False,
            'download_date': self.downloaded if self.downloaded else None,
            'entry_original_url': self.entry_original_url,
            'entry_title': self.entry_title,
            'entry_url': self.entry_url,
            'id': self.id,
            'imdb_id': self.imdb_id,
            'tmdb_id': self.tmdb_id,
            'quality': self.quality,
            'title': self.title,
            'queue_name:': self.queue_name
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
                    'queue_name': {'type': 'string'}
                },
                'required': ['action'],
                'additionalProperties': False,
                'deprecated': 'movie_queue plugin is deprecated. Please switch to using movie_list'
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

        queue_name = config.get('queue_name', 'default')

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

        movie = task.session.query(QueuedMovie).filter(QueuedMovie.downloaded == None).filter(
            QueuedMovie.queue_name == queue_name).filter(or_(*conditions)).first()
        if movie and movie.quality_req.allows(quality):
            return movie

    def on_task_output(self, task, config):
        if not config:
            return
        if not isinstance(config, dict):
            config = {'action': config}
        config.setdefault('queue_name', 'default')
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
            kwargs['queue_name'] = config.get('queue_name')
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
def queue_add(title=None, imdb_id=None, tmdb_id=None, quality=None, session=None, queue_name='default'):
    """
    Add an item to the queue with the specified quality requirements.

    One or more of `title` `imdb_id` or `tmdb_id` must be specified when calling this function.

    :param title: Title of the movie. (optional)
    :param imdb_id: IMDB id for the movie. (optional)
    :param tmdb_id: TMDB id for the movie. (optional)
    :param quality: A QualityRequirements object defining acceptable qualities.
    :param queue_name: Name of movie queue to get items from
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
    item = session.query(QueuedMovie).filter(and_((func.lower(QueuedMovie.queue_name) == queue_name.lower()),
                                                  or_(and_(QueuedMovie.imdb_id != None, QueuedMovie.imdb_id == imdb_id),
                                                      and_(QueuedMovie.tmdb_id != None,
                                                           QueuedMovie.tmdb_id == tmdb_id)))).first()
    if not item:
        item = QueuedMovie(title=title, imdb_id=imdb_id, tmdb_id=tmdb_id, quality=quality.text, queue_name=queue_name)
        session.add(item)
        session.commit()
        log.info('Adding %s to movie queue %s with quality=%s.', title, queue_name, quality)
        return item.to_dict()
    else:
        if item.downloaded:
            raise QueueError('ERROR: %s has already been queued and downloaded' % title, errno=1)
        else:
            raise QueueError('ERROR: %s is already in the queue %s' % (title, queue_name), errno=1)


@with_session
def queue_del(title=None, imdb_id=None, tmdb_id=None, session=None, movie_id=None, queue_name='default'):
    """
    Delete the given item from the queue.

    :param title: Movie title
    :param imdb_id: Imdb id
    :param tmdb_id: Tmdb id
    :param session: Optional session to use, new session used otherwise
    :param queue_name: Name of movie queue to get items from
    :return: Title of forgotten movie
    :raises QueueError: If queued item could not be found with given arguments
    """
    log.debug('queue_del - title=%s, imdb_id=%s, tmdb_id=%s, movie_id=%s, queue_name=%s',
              title, imdb_id, tmdb_id, movie_id, queue_name)
    query = session.query(QueuedMovie).filter(func.lower(QueuedMovie.queue_name) == queue_name.lower())
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
            'title=%s, imdb_id=%s, tmdb_id=%s, movie_id=%s not found in queue %s' % (
                title, imdb_id, tmdb_id, movie_id, queue_name))
    except MultipleResultsFound:
        raise QueueError('title=%s, imdb_id=%s, tmdb_id=%s, movie_id=%s matches multiple results in queue %s' %
                         (title, imdb_id, tmdb_id, movie_id, queue_name))


@with_session
def queue_clear(queue_name='default', session=None):
    """Deletes waiting movies from queue"""
    results = queue_get(downloaded=False, queue_name=queue_name, session=session)
    for res in results:
        session.delete(res)


@with_session
def queue_forget(title=None, imdb_id=None, tmdb_id=None, session=None, movie_id=None, queue_name='default'):
    """
    Forget movie download  from the queue.

    :param title: Movie title
    :param imdb_id: Imdb id
    :param tmdb_id: Tmdb id
    :param session: Optional session to use, new session used otherwise
    :param queue_name: Name of movie queue to get items from
    :return: Title of forgotten movie
    :raises QueueError: If queued item could not be found with given arguments
    """
    log.debug('queue_forget - title=%s, imdb_id=%s, tmdb_id=%s, movie_id=%s, queue_name=%s', title, imdb_id, tmdb_id,
              movie_id, queue_name)
    query = session.query(QueuedMovie).filter(func.lower(QueuedMovie.queue_name) == queue_name.lower())
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
        if not item.downloaded:
            raise QueueError(message=('%s is not marked as downloaded' % title), errno=1)
        item.downloaded = None
        return item.to_dict()
    except NoResultFound as e:
        raise QueueError(message=('title=%s, imdb_id=%s, tmdb_id=%s, movie_id=%s, queue_name=%s not found in queue' %
                                  (title, imdb_id, tmdb_id, movie_id, queue_name)), errno=2)


@with_session
def queue_edit(quality, imdb_id=None, tmdb_id=None, session=None, movie_id=None, queue_name='default'):
    """
    :param quality: Change the required quality for a movie in the queue
    :param imdb_id: Imdb id
    :param tmdb_id: Tmdb id
    :param session: Optional session to use, new session used otherwise
    :param queue_name: Name of movie queue to get items from
    :return: Title of edited item
    :raises QueueError: If queued item could not be found with given arguments
    """
    # check if the item is queued
    log.debug('queue_edit - quality=%s, imdb_id=%s, tmdb_id=%s, movie_id=%s, queue_name=%s', quality, imdb_id, tmdb_id,
              movie_id, queue_name)
    query = session.query(QueuedMovie).filter(func.lower(QueuedMovie.queue_name) == queue_name.lower())
    if imdb_id:
        query = session.query(QueuedMovie).filter(QueuedMovie.imdb_id == imdb_id)
    elif tmdb_id:
        query = session.query(QueuedMovie).filter(QueuedMovie.tmdb_id == tmdb_id)
    elif movie_id:
        query = session.query(QueuedMovie).filter(QueuedMovie.id == movie_id)
    try:
        item = query.one()
        item.quality = quality
        session.commit()
        return item.to_dict()
    except NoResultFound as e:
        raise QueueError(
            'imdb_id=%s, tmdb_id=%s, movie_id=%s not found in queue %s' % (imdb_id, tmdb_id, movie_id, queue_name))


@with_session
def queue_get(session=None, downloaded=None, queue_name='default'):
    """
    Get the current movie queue.

    :param session: New session is used it not given
    :param bool downloaded: Whether or not to return only downloaded
    :param queue_name: Name of movie queue to get items from
    :return: List of QueuedMovie objects (detached from session)
    """
    query = session.query(QueuedMovie).filter(func.lower(QueuedMovie.queue_name) == queue_name.lower())
    if downloaded is False:
        return query.filter(QueuedMovie.downloaded == None).all()
    elif downloaded:
        return query.filter(QueuedMovie.downloaded != None).all()
    else:
        return query.all()


@with_session
def get_movie_by_id(movie_id, session=None):
    """
    Return movie item from movie_id
    :param movie_id: ID of queued movie
    :param session: Session
    :return: Dict of movie details
    """
    return session.query(QueuedMovie).filter(QueuedMovie.id == movie_id).one().to_dict()


@with_session
def delete_movie_by_id(movie_id, session=None):
    """
    Deletes movie by its ID
    :param movie_id: ID of queued movie
    :param session: Session
    """
    movie = session.query(QueuedMovie).filter(QueuedMovie.id == movie_id).one()
    session.delete(movie)


@event('plugin.register')
def register_plugin():
    plugin.register(MovieQueue, 'movie_queue', api_ver=2)
