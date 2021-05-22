import datetime
from copy import copy

from loguru import logger
from jinja2 import UndefinedError

from flexget import plugin
from flexget.event import event
from flexget.utils.tools import aggregate_inputs
from flexget.utils.template import evaluate_expression

logger = logger.bind(name='crossmatch')


class CrossMatch:
    """
    Perform action based on item on current task and other inputs.

    Example::

      crossmatch:
        from:
          - rss: http://example.com/
        fields:
          - title
        action: reject
        exact: yes
        case_sensitive: yes
    """

    schema = {
        'type': 'object',
        'properties': {
            'fields': {'type': 'array', 'items': {'type': 'string'}, 'default': []},
            'expressions': {'type': 'array', 'items': {'type': 'string'}, 'default': []},
            'action': {'enum': ['accept', 'reject']},
            'from': {'type': 'array', 'items': {'$ref': '/schema/plugins?phase=input'}},
            'exact': {'type': 'boolean', 'default': True},
            'all_fields': {'type': 'boolean', 'default': False},
            'case_sensitive': {'type': 'boolean', 'default': True},
        },
        'required': ['action', 'from'],
        'additionalProperties': False,
    }

    def on_task_filter(self, task, config):

        fields = config.get('fields', [])
        expressions = config.get('expressions', [])
        action = config['action']
        all_fields = config['all_fields']

        if not task.entries:
            logger.trace('Stopping crossmatch filter because of no entries to check')
            return

        match_entries = aggregate_inputs(task, config['from'])

        # perform action on intersecting entries
        for entry in task.entries:
            for generated_entry in match_entries:
                logger.trace('checking if {} matches {}', entry['title'], generated_entry['title'])

                common_filds = self.entry_intersects(
                    entry,
                    generated_entry,
                    fields,
                    config.get('exact'),
                    config.get('case_sensitive'),
                )

                matched_expression = self.match_expression(
                    entry,
                    generated_entry,
                    expressions,
                )

                common = common_filds + matched_expression

                if common and (not all_fields or len(common) == (len(fields) + len(expressions))):
                    msg = f'intersects with {generated_entry["title"]} on '

                    if common_filds:
                        msg += f'field(s) {", ".join(common_filds)}'

                    if matched_expression:
                        if common_filds:
                            msg += ' and '

                        msg += f'expressions(s) {", ".join(matched_expression)}'

                    for key in generated_entry:
                        if key not in entry:
                            entry[key] = generated_entry[key]
                    if action == 'reject':
                        entry.reject(msg)
                    if action == 'accept':
                        entry.accept(msg)

    def match_expression(self, e1, e2, expressions=None):
        """
        :param e1: First :class:`flexget.entry.Entry`
        :param e2: Second :class:`flexget.entry.Entry`
        :param expressions: List of expressions which are checked
        :return: List of field expressions matched
        """
        if expressions is None:
            expressions = []

        matched_expression = []

        for expression in expressions:
            e1 = self.update_entry(e1)
            e2 = self.update_entry(e2)

            eval_locals = {
                'input_entry': self.update_entry(e1),
                'from_entry': self.update_entry(e2),
            }

            try:
                passed = evaluate_expression(expression, eval_locals)
                if passed:
                    logger.debug('Matched expression `{}`', expression)
                    matched_expression.append(expression)
            except UndefinedError as e:
                # Extract the name that did not exist
                missing_field = e.args[0].split('\'')[1]
                logger.debug(
                    'Missing the field `{}` in expression `{}`', missing_field, expression
                )
            except Exception as e:
                logger.error(
                    'Error occurred while evaluating expression `{}`. ({})', expression, e
                )

        return matched_expression

    def entry_intersects(self, e1, e2, fields=None, exact=True, case_sensitive=True):
        """
        :param e1: First :class:`flexget.entry.Entry`
        :param e2: Second :class:`flexget.entry.Entry`
        :param fields: List of fields which are checked
        :return: List of field names in common
        """

        if fields is None:
            fields = []

        common_fields = []

        for field in fields:
            # Doesn't really make sense to match if field is not in both entries
            if field not in e1 or field not in e2:
                logger.trace('field {} is not in both entries', field)
                continue

            if not case_sensitive and isinstance(e1[field], str):
                v1 = e1[field].lower()
            else:
                v1 = e1[field]
            if not case_sensitive and isinstance(e1[field], str):
                v2 = e2[field].lower()
            else:
                v2 = e2[field]

            try:
                if v1 == v2 or not exact and (v2 in v1 or v1 in v2):
                    common_fields.append(field)
                else:
                    logger.trace('not matching')
            except TypeError as e:
                # argument of type <type> is not iterable
                logger.trace('error matching fields: {}', str(e))

        return common_fields

    def update_entry(self, entry):
        new_entry = copy(entry)
        new_entry.update(
            {
                'has_field': lambda f: f in entry,
                'timedelta': datetime.timedelta,
                'utcnow': datetime.datetime.utcnow(),
                'now': datetime.datetime.now(),
            }
        )

        return new_entry


@event('plugin.register')
def register_plugin():
    plugin.register(CrossMatch, 'crossmatch', api_ver=2)
