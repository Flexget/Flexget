from __future__ import unicode_literals, division, absolute_import
import logging
from argparse import ArgumentError, Action

from sqlalchemy.exc import OperationalError

from flexget.utils import qualities
from flexget.utils.tools import console, str_to_boolean
from flexget.plugin import DependencyError, register_plugin, register_parser_option

try:
    from flexget.plugins.filter.movie_queue import QueueError, queue_add, queue_del, queue_get, queue_forget, parse_what
except ImportError:
    raise DependencyError(issued_by='cli_movie_queue', missing='movie_queue')

log = logging.getLogger('cli_movie_queue')

ACTIONS = ['add', 'del', 'forget', 'list', 'downloaded', 'clear']
USAGE = '(%s) [NAME|IMDB_ID|tmdb_id=TMDB_ID] [QUALITY] [FORCE]' % '|'.join(ACTIONS)


class MovieQueueManager(object):
    """
    Handle IMDb queue management; add, delete and list
    """

    def on_process_start(self, task):
        """Handle --movie-queue management"""

        if not getattr(task.manager.options, 'movie_queue', False):
            return

        task.manager.disable_tasks()
        options = task.manager.options.movie_queue

        if options['action'] == 'list':
            self.queue_list(task.session)
            return

        # If the action affects make sure all entries are processed again next run.
        task.manager.config_changed()

        if options['action'] == 'downloaded':
            self.queue_list(task.session, downloaded=True)
            return

        if options['action'] == 'clear':
            self.clear(task.session)
            return

        if options['action'] == 'del':
            try:
                what = parse_what(options['what'], lookup=False)
                title = queue_del(**what)
            except QueueError as e:
                console('ERROR: %s' % e.message)
            else:
                console('Removed %s from queue' % title)
            return

        if options['action'] == 'forget':
            try:
                what = parse_what(options['what'], lookup=False)
                title = queue_forget(**what)
            except QueueError as e:
                console('ERROR: %s' % e.message)
            else:
                console('Forgot that %s was downloaded. Movie will be downloaded again.' % title)
            return

        if options['action'] == 'add':
            # Adding to queue requires a lookup for missing information
            what = {}
            try:
                what = parse_what(options['what'])
            except QueueError as e:
                console('ERROR: %s' % e.message)

            if not what.get('title') or not (what.get('imdb_id') or what.get('tmdb_id')):
                console('could not determine movie')  # TODO: Rethink errors
                return

            try:
                added = queue_add(title=what['title'], imdb_id=what['imdb_id'],
                                  tmdb_id=what['tmdb_id'], quality=options['quality'], force=options['force'])
            except QueueError as e:
                console(e.message)
                if e.errno == 1:
                    # This is an invalid quality error, display some more info
                    # TODO: Fix this error?
                    #console('Recognized qualities are %s' % ', '.join([qual.name for qual in qualities.all()]))
                    console('ANY is the default and can also be used explicitly to specify that quality should be ignored.')
            except OperationalError:
                log.critical('OperationalError')

    def queue_list(self, session, downloaded=False):
        """List movie queue"""

        items = queue_get(session=session, downloaded=downloaded)
        console('-' * 79)
        console('%-10s %-7s %-37s %-15s %s' % ('IMDB id', 'TMDB id', 'Title', 'Quality', 'Force'))
        console('-' * 79)
        for item in items:
            console('%-10s %-7s %-37s %-15s %s' % (item.imdb_id, item.tmdb_id, item.title, item.quality, item.immortal))

        if not items:
            console('No results')

        console('-' * 79)

    def clear(self, session):
        """Delete movie queue"""

        items = queue_get(session=session, downloaded=False)
        console('Removing the following movies from movie queue:')
        console('-' * 79)
        for item in items:
            console(item.title)
            queue_del(title=item.title)

        if not items:
            console('No results')

        console('-' * 79)


class MovieQueueAction(Action):
    def __call__(self, parser, namespace, values, option_string=None):
        options = namespace.movie_queue = {}

        # Assume 'list' if no action was given
        if not values:
            values = ['list']

        if values[0].lower() not in ACTIONS:
            raise ArgumentError(self, '`%s` is not a valid action.\nUsage: ' % values[0] + USAGE)
        options['action'] = values[0].lower()

        if len(values) == 1:
            if options['action'] not in ('list', 'downloaded', 'clear'):
                raise ArgumentError(self, 'You must specify the movie.\nUsage: ' + USAGE)

        # 2, args is the minimum allowed (operation + item) for actions other than list
        if len(values) >= 2:
            options['what'] = values[1]

        # 3, quality
        if len(values) >= 3:
            try:
                options['quality'] = qualities.Requirements(values[2])
            except ValueError as e:
                raise ArgumentError(self, '`%s` is an invalid quality requirement string: %s' %
                                    (values[2], e.message))
        else:
            options['quality'] = qualities.Requirements('any')
            # TODO: Get default from config somehow?
            # why not use the quality user has queued most, ie option called 'auto' ?
            # and if none is queued default to something good like '720p bluray'

        # 4, force download
        if len(values) >= 4:
            options['force'] = str_to_boolean(values[3])
        else:
            options['force'] = True

        if len(values) > 4:
            raise ArgumentError(self, 'Too many arguments passed.\nUsage: ' + USAGE)


register_plugin(MovieQueueManager, 'movie_queue_manager', builtin=True)
register_parser_option('--movie-queue', nargs='*', metavar=('ACTION', 'TITLE'),
                       action=MovieQueueAction, help=USAGE)
