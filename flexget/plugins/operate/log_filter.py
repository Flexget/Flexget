from __future__ import unicode_literals, division, absolute_import
import logging

from flexget import plugin
from flexget.event import event

log = logging.getLogger('logfilter')


class MyFilter(logging.Filter):
    
    def __init__(self, term):
        self.term = term
    
    def filter(self, record):
        return not (isinstance(record.msg, basestring) and self.term in record.msg)


class MyLogFilter(object):
    """
    Prevent entries with specific text from being logged.
    
    Example::

      log_filter:
        some.context:
          - in a galaxy
          - far far away
        another.context:
          - whatever text
          - what the heck?
    
    """
    
    schema = {
        'type': 'object',
        'additionalProperties': {
            'type': 'array',
            'items': {'type': 'string'},
            'minItems': 1,
            'additionalProperties': 'string'
        }
    }
    
    filters = None
    
    @plugin.priority(255)
    def on_task_start(self, task, config):
        self.filters = {}
        for k in config.keys():
            self.filters[k] = []
            for s in config[k]:
                f = MyFilter(s)
                logging.getLogger(k).addFilter(f)
                log.debug('Log filter %d added (context "%s", term "%s")' % (id(f), k, s))
                self.filters[k].append(f)
    
    @plugin.priority(-255)
    def on_task_exit(self, task, config):
        if self.filters is None:
            return
        for k in self.filters.keys():
            for f in self.filters[k]:
                logging.getLogger(k).removeFilter(f)
                log.debug('Log filter %d removed' % (id(f)))
    
    on_task_abort = on_task_exit


@event('plugin.register')
def register_plugin():
    plugin.register(MyLogFilter, 'log_filter', api_ver=2)
