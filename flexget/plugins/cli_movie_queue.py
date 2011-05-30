import logging
from optparse import OptionValueError
from sqlalchemy.exc import OperationalError
from flexget.utils import qualities
from flexget.utils.tools import console, str_to_boolean
from flexget.plugin import DependencyError, register_plugin, register_parser_option

try:
    from flexget.plugins.filter.movie_queue import QueueError, queue_add, queue_del, queue_list, parse_what
except ImportError:
    raise DependencyError(issued_by='cli_movie_queue', missing='movie_queue')

log = logging.getLogger('cli_movie_queue')


class MovieQueueManager(object):
    """
    Handle IMDb queue management; add, delete and list
    """

    @staticmethod
    def optik_movie_queue(option, opt, value, parser):
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
            console('could not determine movie') # TODO: Rethink errors
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


register_plugin(MovieQueueManager, 'movie_queue_manager', builtin=True)
register_parser_option('--movie-queue', action='callback',
                       callback=MovieQueueManager.optik_movie_queue,
                       help='(add|del|list) [NAME|IMDB_ID|tmdb_id=TMDB_ID] [QUALITY] [FORCE]')
