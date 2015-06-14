from __future__ import unicode_literals, division, absolute_import
import logging
from flask import render_template, Blueprint

from flexget.ui import register_plugin, manager, menu

log = logging.getLogger('ui.schedule')
schedule = Blueprint('schedule', __name__)

@schedule.context_processor
def get_intervals():
    config = manager.config.setdefault('schedules', {})
    config_tasks = config.setdefault('tasks', {})
    task_schedules = []
    for task in set(config_tasks) | set(manager.tasks):
        task_schedules.append(
            {'name': task,
             'enabled': task in config_tasks,
             'schedule': config_tasks.get(task, ''),
             'valid': task in manager.tasks})
    default_schedule = {'enabled': 'default' in config, 'schedule': config.get('default', '')}
    return {'default_schedule': default_schedule, 'task_schedules': task_schedules}


@schedule.route('/', methods=['POST', 'GET'])
@menu.register_menu(schedule, '.schedule', 'Schedule', order=20)
def index():
    return render_template('schedule/schedule.html')


register_plugin(schedule)
