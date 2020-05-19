from loguru import logger

from flexget import options, plugin
from flexget.entry import EntryState
from flexget.event import event
from flexget.task import logger as task_logger
from flexget.utils.log import log_once

logger = logger.bind(name='verbose')


class Verbose:
    """
    Verbose entry accept, reject and failure
    """

    # Run first thing after input phase
    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_metainfo(self, task, config):
        if task.options.silent:
            return
        for entry in task.all_entries:
            entry.on_accept(self.verbose_details, task=task, act=EntryState.ACCEPTED, reason='')
            entry.on_reject(self.verbose_details, task=task, act=EntryState.REJECTED, reason='')
            entry.on_fail(self.verbose_details, task=task, act=EntryState.FAILED, reason='')

    @staticmethod
    def verbose_details(entry, task=None, act: EntryState = None, reason=None, **kwargs):
        msg = f"`{entry['title']}` by {task.current_plugin} plugin"
        if reason:
            msg = f'{msg} because {reason[0].lower() + reason[1:]}'
        task_logger.opt(colors=True).verbose(f"{act.log_markup}: {{}}", msg)

    def on_task_exit(self, task, config):
        if task.options.silent:
            return
        # verbose undecided entries
        if task.options.verbose:
            undecided = False
            for entry in task.entries:
                if entry in task.accepted:
                    continue
                undecided = True
                logger.verbose('UNDECIDED: `{}`', entry['title'])
            if undecided:
                log_once(
                    'Undecided entries have not been accepted or rejected. If you expected these to reach output,'
                    ' you must set up filter plugin(s) to accept them.',
                    logger=logger,
                )


@event('plugin.register')
def register_plugin():
    plugin.register(Verbose, 'verbose', builtin=True, api_ver=2)


@event('options.register')
def register_parser_arguments():
    exec_parser = options.get_parser('execute')
    exec_parser.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        dest='verbose',
        default=False,
        help='verbose undecided entries',
    )
    exec_parser.add_argument(
        '-s',
        '--silent',
        action='store_true',
        dest='silent',
        default=False,
        help='don\'t verbose any actions (accept, reject, fail)',
    )
