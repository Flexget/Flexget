import re

from loguru import logger

from flexget import plugin
from flexget.event import event

logger = logger.bind(name='manipulate')


class Manipulate:
    r"""
    Usage:

      manipulate:
        - <destination field>:
            [find_all]: <boolean>
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

    schema = {
        'type': 'array',
        'items': {
            'type': 'object',
            'additionalProperties': {
                'type': 'object',
                'properties': {
                    'phase': {'enum': ['metainfo', 'filter', 'modify']},
                    'from': {'type': 'string'},
                    'extract': {'type': 'string', 'format': 'regex'},
                    'separator': {'type': 'string'},
                    'remove': {'type': 'boolean'},
                    'find_all': {'type': 'boolean'},
                    'replace': {
                        'type': 'object',
                        'properties': {
                            'regexp': {'type': 'string', 'format': 'regex'},
                            'format': {'type': 'string'},
                        },
                        'required': ['regexp', 'format'],
                        'additionalProperties': False,
                    },
                },
                'additionalProperties': False,
            },
        },
    }

    def on_task_start(self, task, config):
        """
        Separates the config into a dict with a list of jobs per phase.
        Allows us to skip phases without any jobs in them.
        """
        self.phase_jobs = {'filter': [], 'metainfo': [], 'modify': []}
        for item in config:
            for item_config in item.values():
                # Get the phase specified for this item, or use default of metainfo
                phase = item_config.get('phase', 'metainfo')
                self.phase_jobs[phase].append(item)

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_metainfo(self, task, config):
        if not self.phase_jobs['metainfo']:
            # return if no jobs for this phase
            return
        modified = sum(self.process(entry, self.phase_jobs['metainfo']) for entry in task.entries)
        logger.verbose('Modified {} entries.', modified)

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_filter(self, task, config):
        if not self.phase_jobs['filter']:
            # return if no jobs for this phase
            return
        modified = sum(self.process(entry, self.phase_jobs['filter']) for entry in task.entries)
        logger.verbose('Modified {} entries.', modified)

    @plugin.priority(plugin.PRIORITY_FIRST)
    def on_task_modify(self, task, config):
        if not self.phase_jobs['modify']:
            # return if no jobs for this phase
            return
        modified = sum(self.process(entry, self.phase_jobs['modify']) for entry in task.entries)
        logger.verbose('Modified {} entries.', modified)

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
                logger.debug(
                    'field: `{}` from_field: `{}` field_value: `{}`',
                    field,
                    from_field,
                    field_value,
                )
                if config.get('remove'):
                    if field in entry:
                        del entry[field]
                        modified = True
                    continue
                if 'extract' in config:
                    if not field_value:
                        logger.warning('Cannot extract, field `{}` is not present', from_field)
                        continue
                    if config.get('find_all'):
                        match = re.findall(config['extract'], field_value, re.I | re.U)
                        logger.debug('all matches: {}', match)
                        field_value = config.get('separator', ' ').join(match).strip()
                        logger.debug('field `{}` after extract: `{}`', field, field_value)
                    else:
                        match = re.search(config['extract'], field_value, re.I | re.U)
                        if match:
                            groups = [x for x in match.groups() if x is not None]
                            logger.debug('groups: {}', groups)
                            field_value = config.get('separator', ' ').join(groups).strip()
                            logger.debug('field `{}` after extract: `{}`', field, field_value)

                if 'replace' in config:
                    if not field_value:
                        logger.warning('Cannot replace, field `{}` is not present', from_field)
                        continue
                    replace_config = config['replace']
                    regexp = re.compile(replace_config['regexp'], flags=re.I | re.U)
                    field_value = regexp.sub(replace_config['format'], field_value).strip()
                    logger.debug('field `{}` after replace: `{}`', field, field_value)

                if from_field != field or entry[field] != field_value:
                    logger.verbose('Field `{}` is now `{}`', field, field_value)
                    modified = True
                entry[field] = field_value
        return modified


@event('plugin.register')
def register_plugin():
    plugin.register(Manipulate, 'manipulate', api_ver=2)
