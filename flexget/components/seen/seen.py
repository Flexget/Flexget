from __future__ import unicode_literals, division, absolute_import

import logging
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from past.builtins import basestring

from flexget import plugin
from flexget.event import event
from . import db

log = logging.getLogger(__name__)


class FilterSeen(object):
    """
    Remembers previously downloaded content and rejects them in
    subsequent executions. Without this plugin FlexGet would
    download all matching content on every execution.

    This plugin is enabled on all tasks by default.
    See wiki for more information.
    """

    schema = {
        'oneOf': [
            {'type': 'boolean'},
            {'type': 'string', 'enum': ['global', 'local']},
            {
                'type': 'object',
                'properties': {
                    'local': {'type': 'boolean'},
                    'fields': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        "minItems": 1,
                        "uniqueItems": True,
                    },
                },
            },
        ]
    }

    def __init__(self):
        # remember and filter by these fields
        self.fields = ['title', 'url', 'original_url']
        self.keyword = 'seen'

    def prepare_config(self, config):
        if config is None:
            config = {}
        elif isinstance(config, bool):
            if config is False:
                return config
            else:
                config = {'local': False}
        elif isinstance(config, basestring):
            config = {'local': config == 'local'}

        config.setdefault('local', False)
        config.setdefault('fields', self.fields)
        return config

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_filter(self, task, config, remember_rejected=False):
        """Filter entries already accepted on previous runs."""
        config = self.prepare_config(config)
        if config is False:
            log.debug('%s is disabled' % self.keyword)
            return

        fields = config.get('fields')
        local = config.get('local')

        for entry in task.entries:
            # construct list of values looked
            values = []
            for field in fields:
                if field not in entry:
                    continue
                if entry[field] not in values and entry[field]:
                    values.append(str(entry[field]))
            if values:
                log.trace('querying for: %s' % ', '.join(values))
                # check if SeenField.value is any of the values
                found = db.search_by_field_values(
                    field_value_list=values, task_name=task.name, local=local, session=task.session
                )
                if found:
                    log.debug(
                        "Rejecting '%s' '%s' because of seen '%s'"
                        % (entry['url'], entry['title'], found.value)
                    )
                    se = (
                        task.session.query(db.SeenEntry)
                        .filter(db.SeenEntry.id == found.seen_entry_id)
                        .one()
                    )
                    entry.reject(
                        'Entry with %s `%s` is already marked seen in the task %s at %s'
                        % (found.field, found.value, se.task, se.added.strftime('%Y-%m-%d %H:%M')),
                        remember=remember_rejected,
                    )

    def on_task_learn(self, task, config):
        """Remember succeeded entries"""
        config = self.prepare_config(config)
        if config is False:
            log.debug('disabled')
            return

        fields = config.get('fields')
        local = config.get('local')

        if isinstance(config, list):
            fields.extend(config)

        for entry in task.accepted:
            self.learn(task, entry, fields=fields, local=local)
            # verbose if in learning mode
            if task.options.learn:
                log.info("Learned '%s' (will skip this in the future)" % (entry['title']))

    def learn(self, task, entry, fields=None, reason=None, local=False):
        """Marks entry as seen"""
        # no explicit fields given, use default
        if not fields:
            fields = self.fields
        se = db.SeenEntry(entry['title'], str(task.name), reason, local)
        remembered = []
        for field in fields:
            if field not in entry:
                continue
            # removes duplicate values (eg. url, original_url are usually same)
            if entry[field] in remembered:
                continue
            remembered.append(entry[field])
            sf = db.SeenField(str(field), str(entry[field]))
            se.fields.append(sf)
            log.debug("Learned '%s' (field: %s, local: %d)" % (entry[field], field, local))
        # Only add the entry to the session if it has one of the required fields
        if se.fields:
            task.session.add(se)

    def forget(self, task, title):
        """Forget SeenEntry with :title:. Return True if forgotten."""
        se = task.session.query(db.SeenEntry).filter(db.SeenEntry.title == title).first()
        if se:
            log.debug("Forgotten '%s' (%s fields)" % (title, len(se.fields)))
            task.session.delete(se)
            return True


@event('plugin.register')
def register_plugin():
    plugin.register(FilterSeen, 'seen', builtin=True, api_ver=2)
