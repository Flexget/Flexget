from __future__ import unicode_literals, division, absolute_import
import logging
from flexget.utils.log import log_once
from flexget.plugin import register_plugin, register_parser_option
from flexget.task import log as task_log

log = logging.getLogger('verbose')


class Verbose(object):

    """
    Verbose entry accept, reject and failure
    """

    def on_entry_accept(self, task, entry, reason='', **kwargs):
        self.verbose_details(task, action='Accepted', title=entry['title'], reason=reason)

    def on_entry_reject(self, task, entry, reason='', **kwargs):
        self.verbose_details(task, action='Rejected', title=entry['title'], reason=reason)

    def on_entry_fail(self, task, entry, reason='', **kwargs):
        self.verbose_details(task, action='Failed', title=entry['title'], reason=reason)

    def verbose_details(self, task, **kwarg):
        if task.manager.options.silent:
            return
        kwarg['plugin'] = task.current_plugin
        kwarg['action'] = kwarg['action'].upper()

        if kwarg['reason'] is None:
            msg = "%(action)s: `%(title)s` by %(plugin)s plugin"
        else:
            # lower capitalize first letter of reason
            if kwarg['reason'] and len(kwarg['reason']) > 2:
                kwarg['reason'] = kwarg['reason'][0].lower() + kwarg['reason'][1:]
            msg = "%(action)s: `%(title)s` by %(plugin)s plugin because %(reason)s"

        task_log.verbose(msg % kwarg)

    def on_task_exit(self, task):
        if task.manager.options.silent:
            return
        # verbose undecided entries
        if task.manager.options.verbose:
            undecided = False
            for entry in task.entries:
                if entry in task.accepted:
                    continue
                undecided = True
                log.verbose('UNDECIDED: `%s`' % entry['title'])
            if undecided:
                log_once('Undecided entries have not been accepted or rejected. If you expected these to reach output,'
                         ' you must set up filter plugin(s) to accept them.', logger=log)

register_plugin(Verbose, 'verbose', builtin=True)
register_parser_option('-v', '--verbose', action='store_true', dest='verbose', default=False,
                       help='Verbose undecided entries.')
register_parser_option('-s', '--silent', action='store_true', dest='silent', default=False,
                       help='Don\'t verbose any actions (accept, reject, fail).')
