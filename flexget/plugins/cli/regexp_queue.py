from __future__ import unicode_literals, division, absolute_import
from datetime import datetime, timedelta
from string import capwords
from flexget.event import event

from flexget.manager import Session
from flexget.plugin import register_plugin, register_parser_option, DependencyError
from flexget.utils import qualities
from flexget.utils.tools import console

try:
    from flexget.plugins.filter.regexp_queue import (QueuedRegexp,
                                                    queue_add,
                                                    queue_del,
                                                    queue_edit,
                                                    queue_get,
                                                    queue_forget,
                                                    queue_get_single,
                                                    QueueError,
                                                    )
except ImportError:
    raise DependencyError(issued_by='cli_regexp_queue', missing='regexp_queue', message='RegexpQueue commandline interface not loaded')


def cmdline_option(name, *args, **kwargs):
    f = event('manager.startup')
    register_parser_option(name, *args, **kwargs)
    argument_name = name
    if argument_name.startswith('--'):
        argument_name = name[2:]
    argument_name = argument_name.replace('-','_')
    def wrapper(fn):
        def func(manager):
            arg = getattr(manager.options, argument_name, False)
            if arg:
                manager.disable_tasks()
                return fn(manager, arg)
        return f(func)
    return wrapper


class CLIException(Exception):
    pass


class BaseCLI(object):
    @classmethod
    def handle(cls, manager, args):
        if len(args) == 0:
            args = [cls.DEFAULT_ACTION]

        action = args[0]
        args = args[1:]
        try:
            return cls._run(action, manager, args)
        except CLIException as e:
            console('Error: %s' % e.message)
            console('Usage: '+ cls.USAGE)

    @classmethod
    def _run(cls, action, manager, args):
        func = getattr(cls, 'do_%s' % action, None)
        if func:
            return func(manager, args)
        else:
            raise CLIException('Invalid action %s' % action)

    @classmethod
    def register(cls):
        cmdline_option(cls.OPTION_NAME, **cls.KWARGS)(cls.handle)

class RegexpQueueCLI(BaseCLI):
    OPTION_NAME = '--regexp-queue'

    ACTIONS = ['add', 'del', 'forget', 'list', 'downloaded', 'clear']
    DEFAULT_ACTION = 'list'

    USAGE = '(%s) [REGEXP] [QUALITY]' % '|'.join(ACTIONS)

    FORMAT_ITEM = staticmethod(lambda item: '%-20s %-15s' % (item.regexp, item.quality))

    KWARGS = { 'nargs': '*', 'metavar': ('ACTION', 'REGEXP'), 'help': USAGE}

    @staticmethod
    def do_add(manager, args):
        if len(args) < 1:
            raise CLIException('Missing regexp and/or quality parameter')
        regexp, quality = None, None
        if len(args) > 1:
            regexp, quality = args[:2]
        else:
            regexp = args[0]

        if not isinstance(regexp, unicode):
            console('Unknown regexp %s' % regexp)
            return

        # convert quality
        if not isinstance(quality, unicode):
            quality = qualities.Requirements('any')
        else:
            quality = qualities.Requirements(quality)

        try:
            item = queue_add(regexp, quality)
        except QueueError as e:
            console('ERROR: %s' % e.message)
        else:
            console('Added %s to queue.' % regexp)


    @classmethod
    def do_downloaded(cls, manager, args):
        return cls.do_list(manager, args, downloaded=True)

    @classmethod
    def do_list(cls, manager, args, downloaded=False):
        items = queue_get(downloaded=downloaded)
        line = lambda: console('-' * 79)
        line()
        if len(items) > 0:
            map(console, map(cls.FORMAT_ITEM, items))
        else:
            console('No results')

        line()


    @staticmethod
    def do_del(manager, args):
        if len(args) == 0:
            raise CLIException('Missing regexp')

        regexp = args[0]

        try:
            item = queue_del(regexp=regexp)
        except QueueError as e:
            raise CLIException(e.message)

        console('Deleted %s' % regexp)

    @classmethod
    def do_clear(manager, args):
        items = queue_get()
        console('Deleting the following expressions:')
        line = lambda: console('-' * 79)
        line()
        if len(items) > 0:
            for item in items:
                console(cls.FORMAT_ITEM(item))
                queue_del(item.regexp)
        else:
            console('No results')

        line()

    @classmethod
    def do_forget(cls, manager, args):
        if len(args) < 1:
            raise CLIException('Missing regexp to delete')

        regexp = args[0]
        try:
            item = queue_get_single(regexp=regexp)
            queue_forget(regexp=regexp)
        except QueueError as e:
            raise CLIException('QueueError: %s' % e.message)
        console('Forgetting:')
        console(cls.FORMAT_ITEM(item))

RegexpQueueCLI.register()

