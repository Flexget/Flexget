import logging
from optparse import OptionValueError
from sqlalchemy import Column, Integer, String, ForeignKey, or_, select
from sqlalchemy.exc import OperationalError
from flexget import schema
from flexget.manager import Session
from flexget.utils import qualities
from flexget.utils.imdb import extract_id
from flexget.utils.database import quality_synonym, quality_comp_property
from flexget.utils.tools import console, str_to_boolean
from flexget.utils.sqlalchemy_utils import table_exists, table_schema
from flexget.plugin import DependencyError, get_plugin_by_name, register_plugin, register_parser_option
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
                    queue_add(imdb_id=row['imdb_id'], quality=row['quality'], force=row['immortal'])
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
    quality_comp = quality_comp_property('quality')


class FilterMovieQueue(queue_base.FilterQueueBase):

    def matches(self, feed, config, entry):
        # make sure the entry has a movie id field filled
        conditions = []
        # First see if a movie id is already populated
        if entry.get_no_lazy('imdb_id'):
            conditions.append(QueuedMovie.imdb_id == entry['imdb_id'])
        if entry.get_no_lazy('tmdb_id'):
            conditions.append(QueuedMovie.id == entry['tmdb_id'])
        # Otherwise see if there is a lazy field available
        if not conditions:
            if entry.get('imdb_id'):
                conditions.append(QueuedMovie.imdb_id == entry['imdb_id'])
            elif entry.get('tmdb_id'):
                conditions.append(QueuedMovie.id == entry['tmdb_id'])
        # If we still don't have any criteria, try a lookup
        if not conditions:
            try:
                movie = get_plugin_by_name('api_tmdb').instance.lookup(smart_match=entry['title'])
                conditions.append(QueuedMovie.tmdb_id == movie.id)
                if movie.imdb_id:
                    conditions.append(QueuedMovie.imdb_id == movie.imdb_id)
            except (DependencyError, LookupError), e:
                log.debug('Cannot lookup movie info: %s' % e)
                return

        if not conditions:
            log.warning("No movie id could be determined for %s" % entry['title'])
            return

        quality = entry.get('quality', qualities.UNKNOWN)

        return feed.session.query(QueuedMovie).filter(QueuedMovie.downloaded == None).\
                                               filter(or_(*conditions)).\
                                               filter(or_(QueuedMovie.quality == 'ANY',
                                                          QueuedMovie.quality_comp <= quality.value)).first()


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
    if quality.upper() == 'ANY':
        return 'ANY'
    elif qualities.get(quality, False):
        return qualities.common_name(quality)
    else:
        raise QueueError('ERROR! Unknown quality `%s`' % quality, errno=1)


def parse_what(what):
    """Parses needed movie information for a given search string.

    Search string can be one of:
        <Movie Title>: Search based on title
        imdb_id=<IMDB id>: search based on imdb id
        tmdb_id=<TMDB id>: search based on tmdb id"""

    tmdb_lookup = get_plugin_by_name('api_tmdb').instance.lookup

    imdb_id = extract_id(what)
    try:
        if imdb_id:
            movie = tmdb_lookup(imdb_id=imdb_id)
        elif what.startswith('tmdb_id='):
            movie = tmdb_lookup(tmdb_id=what[8:])
        else:
            movie = tmdb_lookup(title=what)
    except LookupError, e:
        raise QueueError(e.message)

    if movie:
        return {'title': movie.name, 'imdb_id': movie.imdb_id, 'tmdb_id': movie.id}
    else:
        raise QueueError('ERROR: Unable to find any such movie from tmdb, use imdb or tmdb id instead.')


# API functions to edit queue
def queue_add(title=None, imdb_id=None, tmdb_id=None, quality='ANY', force=True):
    """Add an item to the queue with the specified quality"""

    if not title or not imdb_id or not tmdb_id:
        # We don't have all the info we need to add movie, do a lookup for more info
        result = parse_what(imdb_id or title)
        title = result['title']
        imdb_id = result['imdb_id']
        tmdb_id = result['tmdb_id']
    quality = validate_quality(quality)

    session = Session()
    try:
        # check if the item is already queued
        item = session.query(QueuedMovie).filter(or_(QueuedMovie.imdb_id == imdb_id, QueuedMovie.tmdb_id == tmdb_id)).\
                                          first()
        if not item:
            item = QueuedMovie(title=title, imdb_id=imdb_id, tmdb_id=tmdb_id, quality=quality, immortal=force)
            session.add(item)
            session.commit()
            return {'title': title, 'imdb_id': imdb_id, 'tmdb_id': tmdb_id, 'quality': quality, 'force': force}
        else:
            raise QueueError('ERROR: %s is already in the queue' % title)
    finally:
        session.close()


def queue_del(imdb_id):
    """Delete the given item from the queue"""

    session = Session()
    try:
        # check if the item is queued
        item = session.query(QueuedMovie).filter(QueuedMovie.imdb_id == imdb_id).first()
        if item:
            title = item.title
            session.delete(item)
            session.commit()
            return title
        else:
            raise QueueError('%s is not in the queue' % imdb_id)
    finally:
        session.close()


def queue_edit(imdb_id, quality):
    """Change the required quality for a movie in the queue"""
    quality = validate_quality(quality)
    session = Session()
    try:
        # check if the item is queued
        item = session.query(QueuedMovie).filter(QueuedMovie.imdb_id == imdb_id).first()
        if item:
            item.quality = quality
            session.commit()
            return item.title
        else:
            raise QueueError('%s is not in the queue' % imdb_id)
    finally:
        session.close()


def queue_list():
    """List IMDb queue"""

    items = queue_get()
    console('-' * 79)
    console('%-10s %-7s %-37s %-15s %s' % ('IMDB id', 'TMDB id', 'Title', 'Quality', 'Force'))
    console('-' * 79)
    for item in items:
        console('%-10s %-7s %-37s %-15s %s' % (item.imdb_id, item.tmdb_id, item.title, item.quality, item.immortal))

    if not items:
        console('Movie queue is empty')

    console('-' * 79)


def queue_get():
    """Get the current IMDb queue.

    Returns:
        List of QueuedMovie objects (detached from session)
    """
    session = Session()
    try:
        return session.query(QueuedMovie).filter(QueuedMovie.downloaded == None).all()
    finally:
        session.close()


class MovieQueueManager(object):
    """
    Handle IMDb queue management; add, delete and list
    """

    @staticmethod
    def optik_imdb_queue(option, opt, value, parser):
        """Callback for Optik, parses --movie-queue options and populates movie_queue options value"""
        options = {}
        usage_error = OptionValueError('Usage: --movie-queue (add|del|list) [IMDB_URL|NAME] [QUALITY] [FORCE]')
        if not parser.rargs:
            raise usage_error

        options['action'] = parser.rargs[0].lower()
        if options['action'] not in ['add', 'del', 'list']:
            raise usage_error

        if len(parser.rargs) == 1:
            if options['action'] != 'list':
                raise usage_error

        # 2 args is the minimum allowed (operation + item) for actions other than list
        if len(parser.rargs) >= 2:
            options['what'] = parser.rargs[1]

        # 3, quality
        if len(parser.rargs) >= 3:
            options['quality'] = parser.rargs[2]
        else:
            options['quality'] = 'ANY' # TODO: Get default from config somehow?

        # 4, force download
        if len(parser.rargs) >= 4:
            options['force'] = str_to_boolean(parser.rargs[3])
        else:
            options['force'] = True

        parser.values.movie_queue = options

    def on_process_start(self, feed):
        """Handle --movie-queue management"""

        if not getattr(feed.manager.options, 'movie_queue', False):
            return

        feed.manager.disable_feeds()
        options = feed.manager.options.movie_queue

        if options['action'] == 'list':
            queue_list()
            return

        # all actions except list require movie info to work
        # Generate imdb_id, tmdb_id and movie title from any single one
        try:
            what = parse_what(options['what'])
            options.update(what)
        except QueueError, e:
            console(e.message)

        if not options.get('title') or not (options.get('imdb_id') or options.get('tmdb_id')):
            console('could not determine movie to add') # TODO: Rethink errors
            return

        try:
            if options['action'] == 'add':
                try:
                    added = queue_add(title=options['title'], imdb_id=options['imdb_id'],
                        tmdb_id=options['tmdb_id'], quality=options['quality'], force=options['force'])
                except QueueError, e:
                    console(e.message)
                    if e.errno == 1:
                        # This is an invalid quality error, display some more info
                        console('Recognized qualities are %s' % ', '.join([qual.name for qual in qualities.all()]))
                        console('ANY is the default and can also be used explicitly to specify that quality should be ignored.')
                else:
                    console('Added %s to queue with quality %s' % (added['title'], added['quality']))
            elif options['action'] == 'del':
                try:
                    title = queue_del(imdb_id=options['imdb_id'])
                except QueueError, e:
                    console(e.message)
                else:
                    console('Removed %s from queue' % title)
        except OperationalError:
            log.critical('OperationalError')


register_plugin(FilterMovieQueue, 'movie_queue', api_ver=2)

register_plugin(MovieQueueManager, 'movie_queue_manager', builtin=True)
register_parser_option('--movie-queue', action='callback',
                       callback=MovieQueueManager.optik_imdb_queue,
                       help='(add|del|list) [IMDB_URL|NAME] [QUALITY] [FORCE]')
