"""
Some Utils to hook interface
"""

from flexget.task import Task
from flexget.entry import Entry
from flexget.utils import json, qualities
from flexget.task import EntryIterator, EntryContainer

WEBHOOK_PLUGIN = 'webhooks'

HOOK_SCHEMA_DATA = {
    'send_data': {
        'oneOf': [
            {'type': 'object', 'minProperties': 1},
            {'type': 'string'},
        ]
    },
}

HOOK_SCHEMA_DEFAULT = {'title': {'type': 'string'}, **HOOK_SCHEMA_DATA}


HOOK_SCHEMA_WEBHOOK_DEFAULT = {
    'host': {
        'type': 'string',
    },
    'endpoint': {
        'type': 'string',
    },
    'method': {'type': 'string', 'enum': ['post', 'get']},
    'headers': {'type': 'object', 'minProperties': 1},
}


ENDPOINT = {
    'STAGE_START': 'start',
    'STAGE_END': 'end',
    'EVENT_PHASE': 'phase',
    'EVENT_PLUGIN': 'plugin',
    'EVENT_TASK': 'task',
}


def strisjson(data):
    """
    Checks if a string is JSON
    """

    if isinstance(data, str):
        try:
            data_test = json.loads(data)
            if isinstance(data_test, (dict, list)):
                return True
        except TypeError:
            return False
        except ValueError:
            return False

    return False


def hooks_data_process(send_data):
    """
    Process the data object from the Hooks
    """

    if not send_data:
        return ''

    if isinstance(send_data, str) and strisjson(send_data):
        send_data = json.loads(send_data)
    else:
        send_data = jsonify(send_data)

    return send_data


def webhooks_config_process(config: dict):
    """
    WebHooks default config
    """

    config.setdefault('host', 'localhost')
    config.setdefault('method', 'GET')
    config['method'] = config['method'].upper()

    config.setdefault('headers', {})
    return config


def jsonify(data):
    """
    Ensures that data is JSON friendly
    """

    if isinstance(data, str):
        return data

    try:
        _ = (e for e in data)
    except TypeError:
        return data

    for item in data:
        if isinstance(data[item], (EntryIterator, EntryContainer)):
            lists = list(data[item])
            new_list = []
            for lst in lists:
                dic_list = jsonify(dict(lst))
                new_list.append(dic_list)
            data[item] = new_list
        elif isinstance(data[item], Entry):
            data[item] = jsonify(dict(data[item]))
        elif isinstance(data[item], qualities.Quality):
            data[item] = str(data[item])
        elif isinstance(data[item], dict):
            data[item] = jsonify(data[item])
        else:
            try:
                data[item] = json.dumps(data[item])
                data[item] = json.loads(data[item])
            except TypeError:
                del data[item]

    data.pop('_backlog_snapshot', None)

    return data


def task_to_dict(task: Task):
    """
    Converts Task to dict
    """

    keys = [
        'output',
        'priority',
        'rejected',
        'rerun_count',
        'is_rerun',
        'max_reruns',
        'abort_reason',
        'aborted',
        'accepted',
        'all_entries',
        'current_phase',
        'current_plugin',
        'disabled_phases',
        'disabled_plugins',
        'entries',
        'failed',
        'undecided',
    ]

    task_dict = {}
    for key in keys:
        task_dict[key] = getattr(task, key)

    task_dict['task_name'] = getattr(task, 'name')
    task_dict['task_id'] = getattr(task, 'id')

    return jsonify(task_dict)
