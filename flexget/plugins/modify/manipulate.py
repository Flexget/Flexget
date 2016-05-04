from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import logging
import re

from flexget import plugin
from flexget.event import event

log = logging.getLogger('manipulate')


class Manipulate(object):
    """
    Usage:

      manipulate:
        - <destination field>:
            [phase]: <phase>
            [from]: <source field>
            [extract]: <regexp>
            [separator]: <text>
            [replace]:
              regexp: <regexp>
              format: <regexp>
            [remove]: <boolean>

    Example:

      manipulate:
        - title:
            extract: \[\d\d\d\d\](.*)
    """

    def validator(self):
        from flexget import validator
        root = validator.factory()
        bundle = root.accept('list').accept('dict')
        # prevent invalid indentation level
        bundle.reject_keys(['from', 'extract', 'replace', 'phase'],
            'Option \'$key\' has invalid indentation level. It needs 2 more spaces.')
        edit = bundle.accept_any_key('dict')
        edit.accept('choice', key='phase').accept_choices(['metainfo', 'filter'], ignore_case=True)
        edit.accept('text', key='from')
        edit.accept('regexp', key='extract')
        edit.accept('text', key='separator')
        edit.accept('boolean', key='remove')
        replace = edit.accept('dict', key='replace')
        replace.accept('regexp', key='regexp', required=True)
        replace.accept('text', key='format', required=True)
        return root

    def on_task_start(self, task, config):
        """
        Separates the config into a dict with a list of jobs per phase.
        Allows us to skip phases without any jobs in them.
        """
        self.phase_jobs = {'filter': [], 'metainfo': []}
        for item in config:
            for item_config in item.values():
                # Get the phase specified for this item, or use default of metainfo
                phase = item_config.get('phase', 'metainfo')
                self.phase_jobs[phase].append(item)

    @plugin.priority(255)
    def on_task_metainfo(self, task, config):
        if not self.phase_jobs['metainfo']:
            # return if no jobs for this phase
            return
        modified = sum(self.process(entry, self.phase_jobs['metainfo']) for entry in task.entries)
        log.verbose('Modified %d entries.' % modified)

    @plugin.priority(255)
    def on_task_filter(self, task, config):
        if not self.phase_jobs['filter']:
            # return if no jobs for this phase
            return
        modified = sum(self.process(entry, self.phase_jobs['filter']) for entry in task.entries + task.rejected)
        log.verbose('Modified %d entries.' % modified)

    def process(self, entry, jobs):
        """Process given jobs from config for an entry.

        :param entry: Entry to modify
        :param jobs: Config items to run on this entry
        :return: True if any fields were modified
        """

        modified = False
        for item in jobs:
            for field, config in item.items():
                from_field = field
                if 'from' in config:
                    from_field = config['from']
                field_value = entry.get(from_field)
                log.debug('field: `%s` from_field: `%s` field_value: `%s`' % (field, from_field, field_value))

                if config.get('remove'):
                    if field in entry:
                        del entry[field]
                        modified = True
                    continue

                if 'extract' in config:
                    if not field_value:
                        log.warning('Cannot extract, field `%s` is not present' % from_field)
                        continue
                    match = re.search(config['extract'], field_value, re.I | re.U)
                    if match:
                        groups = [x for x in match.groups() if x is not None]
                        log.debug('groups: %s' % groups)
                        field_value = config.get('separator', ' ').join(groups).strip()
                        log.debug('field `%s` after extract: `%s`' % (field, field_value))

                if 'replace' in config:
                    if not field_value:
                        log.warning('Cannot replace, field `%s` is not present' % from_field)
                        continue
                    replace_config = config['replace']
                    regexp = re.compile(replace_config['regexp'], flags=re.I | re.U)
                    field_value = regexp.sub(replace_config['format'], field_value).strip()
                    log.debug('field `%s` after replace: `%s`' % (field, field_value))

                if from_field != field or entry[field] != field_value:
                    log.verbose('Field `%s` is now `%s`' % (field, field_value))
                    modified = True
                entry[field] = field_value
        return modified


@event('plugin.register')
def register_plugin():
    plugin.register(Manipulate, 'manipulate', api_ver=2)
