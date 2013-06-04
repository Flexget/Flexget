from __future__ import unicode_literals, division, absolute_import
import logging

from flexget.config_schema import one_or_more
from flexget.plugin import register_plugin, priority

log = logging.getLogger('require_field')


class FilterRequireField(object):
    """
    Rejects entries without imdb url.

    Example::

      require_field: imdb_url
    """

    schema = one_or_more({"type": "string"})

    @priority(32)
    def on_task_filter(self, task, config):
        if isinstance(config, basestring):
            config = [config]
        for entry in task.entries:
            for field in config:
                if not entry.get(field):
                    entry.reject('Required field %s is not present' % field)
                    break


register_plugin(FilterRequireField, 'require_field', api_ver=2)
