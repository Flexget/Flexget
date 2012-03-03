import logging
from sqlalchemy import Column, Integer, String, ForeignKey, or_, and_
from flexget import schema
from flexget.manager import Session
from flexget.utils import qualities
from flexget.utils.imdb import extract_id
from flexget.utils.database import quality_property, with_session
from flexget.utils.sqlalchemy_utils import table_exists, table_schema
from flexget.plugin import DependencyError, get_plugin_by_name, register_plugin
from flexget.event import event

try:
    from flexget.plugins.filter import queue_base
except ImportError:
    raise DependencyError(issued_by='movie_queue', missing='queue_base',
                             message='movie_queue requires the queue_base plugin')

log = logging.getLogger('movie_queue')
Base = schema.versioned_base('movie_queue', 0)


@event('manager.startup')
def migrate_imdb_queue(manager):
    """If imdb_queue table is found, migrate the data to movie_queue"""
    session = Session()
    try:
        if table_exists('imdb_queue', session):
            log.info('Migrating imdb_queue items to movie_queue')
            old_table = table_schema('imdb_queue', session)
            for row in session.execute(old_table.select()):
                try:
                    queue_add(imdb_id=row['imdb_id'], quality=row['quality'], force=row['immortal'], session=session)
                except QueueError, e:
                    log.error('Unable to migrate %s from imdb_queue to movie_queue' % row['title'])
            old_table.drop()
            session.commit()
    finally:
        session.close()


class QueuedMovie(queue_base.QueuedItem, Base):
    __tablename__ = 'movie_queue'
    __mapper_args__ = {'polymorphic_identity': 'movie'}
    id = Column(Integer, ForeignKey('queue.id'), primary_key=True)
    imdb_id = Column(String)
    tmdb_id = Column(Integer)
    quality = Column('quality', String)
    quality_obj = quality_property('quality')


class FilterMovieQueue(queue_base.FilterQueueBase):

    def matches(self, feed, config, entry):
        # Tell tmdb_lookup to add lazy lookup fields if not already present
        try:
            get_plugin_by_name('tmdb_lookup').instance.lookup(entry)
        except DependencyError:
            log.debug('tmdb_lookup is not available, queue will not work if movie ids are not populated')
        try:
            get_plugin_by_name('imdb_lookup').instance.register_lazy_fields(entry)
        except DependencyError:
            log.debug('imdb_lookup is not available, queue will not work if movie ids are not populated')
        # make sure the entry has a movie id field filled
        conditions = []
        # Check if a movie id is already populated before incurring a lazy lookup
        for lazy in [False, True]:
            if entry.get('imdb_id', eval_lazy=lazy):
                conditions.append(QueuedMovie.imdb_id == entry['imdb_id'])
            if entry.get('tmdb_id', eval_lazy=lazy):
                conditions.append(QueuedMovie.tmdb_id == entry['tmdb_id'])
            if conditions:
                break
        if not conditions:
            log.verbose('IMDB and TMDB lookups failed for %s.' % entry['title'])
            return

        quality = entry.get('quality', qualities.UNKNOWN)

        return feed.session.query(QueuedMovie).filter(QueuedMovie.downloaded == None).\
                                               filter(or_(*conditions)).\
                                               filter(QueuedMovie.quality_obj <= quality).first()


class QueueError(Exception):
    """Exception raised if there is an error with a queue operation"""

    # TODO: I think message was removed from exception baseclass and is now masked
    # some other custom exception (DependencyError) had to make so tweaks to make it work ..

    def __init__(self, message, errno=0):
        self.message = message
        self.errno = errno


def validate_quality(quality):
    # Check that the quality is valid
    # Make sure quality is in the format we expect
    if isinstance(quality, qualities.Quality):
        if quality.value <= 0:
            return 'ANY'
        return quality.name
    elif quality.upper() == 'ANY':
        return 'ANY'
    elif qualities.get(quality, False):
        return qualities.common_name(quality)
    else:
        raise QueueError('ERROR! Unknown quality `%s`' % quality, errno=1)


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

    tmdb_lookup = get_plugin_by_name('api_tmdb').instance.lookup

    result = {'title': None, 'imdb_id': None, 'tmdb_id': None}
    result['imdb_id'] = extract_id(what)
    if not result['imdb_id'] and what.startswith('tmdb_id='):
        result['tmdb_id'] = what[8:]
    else:
        result['title'] = what

    if not lookup:
        # If not doing an online lookup we can return here
        return result

    try:
        result['session'] = session
        movie = tmdb_lookup(**result)
    except LookupError, e:
        raise QueueError(e.message)

    if movie:
        return {'title': movie.name, 'imdb_id': movie.imdb_id, 'tmdb_id': movie.id}
    else:
        raise QueueError('ERROR: Unable to find any such movie from tmdb, use imdb or tmdb id instead.')


# API functions to edit queue
@with_session
def queue_add(title=None, imdb_id=None, tmdb_id=None, quality='ANY', force=True, session=None):
    """Add an item to the queue with the specified quality"""

    if not title or not (imdb_id or tmdb_id):
        # We don't have all the info we need to add movie, do a lookup for more info
        result = parse_what(imdb_id or title, session=session)
        title = result['title']
        imdb_id = result['imdb_id']
        tmdb_id = result['tmdb_id']
    quality = validate_quality(quality)

    # check if the item is already queued
    item = session.query(QueuedMovie).filter(or_(and_(QueuedMovie.imdb_id != None, QueuedMovie.imdb_id == imdb_id),
                                                 and_(QueuedMovie.tmdb_id != None, QueuedMovie.tmdb_id == tmdb_id))).\
                                      first()
    if not item:
        item = QueuedMovie(title=title, imdb_id=imdb_id, tmdb_id=tmdb_id, quality=quality, immortal=force)
        session.add(item)
        log.info('Adding %s to movie queue with quality=%s and force=%s.' % (title, quality, force))
        return {'title': title, 'imdb_id': imdb_id, 'tmdb_id': tmdb_id, 'quality': quality, 'force': force}
    else:
        if item.downloaded:
            raise QueueError('ERROR: %s has already been queued and downloaded' % title)
        else:
            raise QueueError('ERROR: %s is already in the queue' % title)


@with_session
def queue_del(what, session=None):
    """Delete the given item from the queue. `what` can be any string accepted by `parse_what`"""

    item = None
    for key, value in parse_what(what, lookup=False).iteritems():
        if value:
            item = session.query(QueuedMovie).filter(getattr(QueuedMovie, key) == value).first()
            break
    if item:
        title = item.title
        session.delete(item)
        return title
    else:
        raise QueueError('%s is not in the queue' % what)


@with_session
def queue_edit(imdb_id, quality, session=None):
    """Change the required quality for a movie in the queue"""
    quality = validate_quality(quality)
    # check if the item is queued
    item = session.query(QueuedMovie).filter(QueuedMovie.imdb_id == imdb_id).first()
    if item:
        item.quality = quality
        session.commit()
        return item.title
    else:
        raise QueueError('%s is not in the queue' % imdb_id)


@with_session
def queue_get(session=None, downloaded=False):
    """Get the current IMDb queue.

    KWArgs:
        session: new session is used it not given
        downloaded: boolean whether or not to return only downloaded

    Returns:
        List of QueuedMovie objects (detached from session)
    """
    if not downloaded:
        return session.query(QueuedMovie).filter(QueuedMovie.downloaded == None).all()
    else:
        return session.query(QueuedMovie).filter(QueuedMovie.downloaded != None).all()


register_plugin(FilterMovieQueue, 'movie_queue', api_ver=2)
