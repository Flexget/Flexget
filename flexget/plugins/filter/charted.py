import logging
from flexget import plugin
from flexget.event import event
from flexget.utils.log import log_once

log = logging.getLogger('charted')


class FilterCharts(object):
    schema = {
        'type': 'object',
        'properties': {
            'provider': {'type': 'string'},
            'max_rank': {'type': 'integer'},
            'max_best_rank': {'type': 'integer'},
            'min_charted_weeks': {'type': 'integer'}
        },
        'additionalProperties': False,
        'required': ['provider']
    }

    def on_task_filter(self, task, config):
        """
        :type task: flexget.task.Task
        """
        provider = config['provider']
        rank_field = 'charts_%s_rank' % provider
        best_rank_field = 'charts_%s_best_rank' % provider
        weeks_field = 'charts_%s_weeks' % provider
        for entry in task.undecided:
            reasons = []
            if 'max_rank' in config:
                rank = entry.get(rank_field)
                if rank is None:
                    reasons.append('max_rank (uncharted)')
                else:
                    if rank > config['max_rank']:
                        reasons.append('max_rank (%s > %s)' % (rank, config['max_rank']))

            if 'max_best_rank' in config:
                best_rank = entry.get(best_rank_field)
                if best_rank is None:
                    reasons.append('max_best_rank (new entry or uncharted)')
                else:
                    if best_rank > config['max_best_rank']:
                        reasons.append('max_best_rank (%s > %s)' % (best_rank, config['max_best_rank']))

            if 'min_charted_weeks' in config:
                weeks = entry.get(weeks_field)
                if weeks is None:
                    reasons.append('min_charted_weeks (new entry or uncharted)')
                else:
                    if weeks < config['min_charted_weeks']:
                        reasons.append('min_charted_weeks (%s < %s)' % (weeks, config['min_charted_weeks']))

            if reasons:
                msg = 'Didn\'t accept `%s` because of rule(s) %s' % \
                      (entry.get('title', None) , ', '.join(reasons))
                if task.options.debug:
                    log.debug(msg)
                else:
                    if task.options.cron:
                        log_once(msg, log)
                    else:
                        log.info(msg)
            else:
                log.debug('Accepting %s' % entry.get('title'))
                entry.accept()

@event('plugin.register')
def register_plugin():
    plugin.register(FilterCharts, 'charted', api_ver=2)
