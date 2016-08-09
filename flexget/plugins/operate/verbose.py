from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging

from flexget import options, plugin
from flexget.event import event
from flexget.task import log as task_log
from flexget.utils.log import log_once

log = logging.getLogger('verbose')


class Verbose(object):
    """
    Verbose entry accept, reject and failure
    """

    # Run first thing after input phase
    @plugin.priority(255)
    def on_task_metainfo(self, task, config):
        if task.options.silent:
            return
        for entry in task.all_entries:
            entry.on_accept(self.verbose_details, task=task, act='accepted', reason='')
            entry.on_reject(self.verbose_details, task=task, act='rejected', reason='')
            entry.on_fail(self.verbose_details, task=task, act='failed', reason='')

    def verbose_details(self, entry, task=None, act=None, reason=None, **kwargs):
        msg = "%s: `%s` by %s plugin" % (act.upper(), entry['title'], task.current_plugin)
        if reason:
            msg += ' because %s' % reason[0].lower() + reason[1:]

        task_log.verbose(msg)

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
                log.verbose('UNDECIDED: `%s`' % entry['title'])
            if undecided:
                log_once('Undecided entries have not been accepted or rejected. If you expected these to reach output,'
                         ' you must set up filter plugin(s) to accept them.', logger=log)


@event('plugin.register')
def register_plugin():
    plugin.register(Verbose, 'verbose', builtin=True, api_ver=2)


@event('options.register')
def register_parser_arguments():
    exec_parser = options.get_parser('execute')
    exec_parser.add_argument('-v', '--verbose', action='store_true', dest='verbose', default=False,
                             help='verbose undecided entries')
    exec_parser.add_argument('-s', '--silent', action='store_true', dest='silent', default=False,
                             help='don\'t verbose any actions (accept, reject, fail)')
