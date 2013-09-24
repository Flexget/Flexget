from __future__ import unicode_literals, division, absolute_import
import datetime
import logging

from flexget.event import event
from flexget.plugin import register_plugin, priority
from flexget.utils.tools import parse_timedelta

log = logging.getLogger('interval')


class PluginInterval(object):
    """
        Allows specifying minimum interval for task execution.

        Format: [n] [minutes|hours|days|weeks]

        Example:

        interval: 7 days
    """

    def validator(self):
        from flexget import validator
        return validator.factory('interval')

    @priority(255)
    def on_task_start(self, task, config):
        # Allow reruns
        if task.is_rerun:
            return
        if task.manager.options.execute.learn:
            log.info('Ignoring task %s interval for --learn' % task.name)
            return
        last_time = task.simple_persistence.get('last_time')
        if not last_time:
            log.info('No previous run recorded, running now')
        elif task.manager.options.execute.interval_ignore:
            log.info('Ignoring interval because of --now')
        else:
            log.debug('last_time: %r' % last_time)
            log.debug('interval: %s' % config)
            next_time = last_time + parse_timedelta(config)
            log.debug('next_time: %r' % next_time)
            if datetime.datetime.now() < next_time:
                log.debug('interval not met')
                log.verbose('Interval %s not met on task %s. Use --now to override.' % (config, task.name))
                task.abort('Interval not met', silent=True)
                return
        log.debug('interval passed')
        task.simple_persistence['last_time'] = datetime.datetime.now()


register_plugin(PluginInterval, 'interval', api_ver=2)


@event('register_parser_arguments')
def register_parser_arguments(core_parser):
    core_parser.get_subparser('execute').add_argument('--now', action='store_true', dest='interval_ignore', default=False,
                                                   help='Ignore interval(s)')
