from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import copy

from flask import request, jsonify

from flexget.manager import manager
from flexget.plugins.daemon.scheduler import schedule_schema, main_schema, scheduler, scheduler_job_map
from flexget.api import api, APIResource

schedule_api = api.namespace('schedules', description='Task Scheduler')

# SwaggerUI does not yet support anyOf or oneOf
schedule_schema = copy.deepcopy(schedule_schema)
schedule_schema['properties']['id'] = {'type': 'integer'}
api_schedule_schema = api.schema('schedules.schedule', schedule_schema)
api_schedules_list_schema = api.schema('schedules.list', {
    'type': 'object',
    'properties': {
        'schedules': {
            'type': 'array',
            'items': schedule_schema
        }
    }
})


def _schedule_by_id(schedule_id):
    for schedule in manager.config.get('schedules', []):
        if id(schedule) == schedule_id:
            schedule = schedule.copy()
            schedule['id'] = schedule_id
            return schedule


schedule_desc = "Schedule ID changes upon daemon restart. The schedules object supports either interval or schedule" \
                " (cron) objects, see the model definition for details. Tasks also support string or list " \
                "(Not displayed as Swagger does yet not support anyOf or oneOf."


@schedule_api.route('/')
@api.doc(description=schedule_desc)
class SchedulesAPI(APIResource):
    @api.response(200, model=api_schedules_list_schema)
    def get(self, session=None):
        """ List schedules """
        schedule_list = []
        if 'schedules' not in manager.config or not manager.config['schedules']:
            return jsonify({'schedules': []})

        for schedule in manager.config['schedules']:
            # Copy the object so we don't apply id to the config
            schedule_id = id(schedule)
            schedule = schedule.copy()
            schedule['id'] = schedule_id
            schedule_list.append(schedule)

        return {'schedules': schedule_list}

    @api.validate(api_schedule_schema, description='Schedule Object')
    @api.response(201, model=api_schedule_schema)
    def post(self, session=None):
        """ Add new schedule """
        data = request.json

        if 'schedules' not in manager.config or not manager.config['schedules']:
            # Schedules not defined or are disabled, enable as one is being created
            manager.config['schedules'] = []

        manager.config['schedules'].append(data)
        new_schedule = _schedule_by_id(id(data))

        if not new_schedule:
            return {'error': 'schedule went missing after add'}, 500

        manager.save_config()
        manager.config_changed()
        return {'schedule': new_schedule}, 201


@schedule_api.route('/<int:schedule_id>/')
@api.doc(params={'schedule_id': 'ID of Schedule'})
@api.doc(description=schedule_desc)
class ScheduleAPI(APIResource):
    @api.response(200, model=api_schedule_schema)
    @api.response(404, description='Schedule not found')
    def get(self, schedule_id, session=None):
        """ Get schedule details """
        schedule = _schedule_by_id(schedule_id)
        if not schedule:
            return {'error': 'schedule not found'}, 404

        job_id = scheduler_job_map.get(schedule_id)
        if job_id:
            job = scheduler.get_job(job_id)
            if job:
                schedule['next_run_time'] = job.next_run_time

        return jsonify(schedule)

    def _get_schedule(self, schedule_id):
        for i in range(len(manager.config.get('schedules', []))):
            if id(manager.config['schedules'][i]) == schedule_id:
                return manager.config['schedules'][i]

    def _update_schedule(self, existing, update, merge=False):
        if 'id' in update:
            del update['id']

        if not merge:
            existing.clear()

        existing.update(update)
        manager.save_config()
        manager.config_changed()
        return existing

    @api.validate(api_schedule_schema, description='Updated Schedule Object')
    @api.response(200, model=api_schedule_schema)
    @api.response(404, description='Schedule not found')
    def put(self, schedule_id, session=None):
        """ Update schedule """
        data = request.json
        schedule = self._get_schedule(schedule_id)

        if not schedule:
            return {'detail': 'invalid schedule id'}, 404

        new_schedule = self._update_schedule(schedule, data)
        return jsonify({'schedule': new_schedule})

    @api.response(404, description='Schedule not found')
    @api.response(200, description='Schedule deleted')
    def delete(self, schedule_id, session=None):
        """ Delete a schedule """
        for i in range(len(manager.config.get('schedules', []))):
            if id(manager.config['schedules'][i]) == schedule_id:
                del manager.config['schedules'][i]
                manager.save_config()
                manager.config_changed()
                return {}, 200

        return {'error': 'Schedule not found'}, 404
