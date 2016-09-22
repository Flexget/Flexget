from __future__ import unicode_literals, division, absolute_import
from builtins import *  # pylint: disable=unused-import, redefined-builtin

import copy

from flask import request, jsonify

from flexget.plugins.daemon.scheduler import schedule_schema, scheduler, scheduler_job_map
from flexget.api import api, APIResource
from flexget.api.app import NotFoundError, APIError, base_message_schema, success_response, etag

schedule_api = api.namespace('schedules', description='Task Scheduler')


class ObjectsContainer(object):
    # SwaggerUI does not yet support anyOf or oneOf
    schedule_object = copy.deepcopy(schedule_schema)
    schedule_object['properties']['id'] = {'type': 'integer'}
    schedule_object['maxProperties'] += 1

    schedules_list = {'type': 'array', 'items': schedule_object}


base_schedule_schema = api.schema('schedules.base', schedule_schema)
api_schedule_schema = api.schema('schedules.schedule', ObjectsContainer.schedule_object)
api_schedules_list_schema = api.schema('schedules.list', ObjectsContainer.schedules_list)


def _schedule_by_id(schedule_id, schedules):
    for idx, schedule in enumerate(schedules):
        if schedule and id(schedule) == schedule_id:
            schedule = schedule.copy()
            schedule['id'] = schedule_id
            return schedule, idx
    return None, None


schedule_desc = "Schedule ID changes upon daemon restart. The schedules object supports either interval or schedule" \
                " (cron) objects, see the model definition for details. Tasks also support string or list " \
                "(Not displayed as Swagger does yet not support anyOf or oneOf."


@schedule_api.route('/')
@api.doc(description=schedule_desc)
class SchedulesAPI(APIResource):
    @etag
    @api.response(200, model=api_schedules_list_schema)
    def get(self, session=None):
        """ List schedules """
        schedule_list = []
        if 'schedules' not in self.manager.config or not self.manager.config['schedules']:
            return jsonify(schedule_list)

        for schedule in self.manager.config['schedules']:
            # Copy the object so we don't apply id to the config
            schedule_id = id(schedule)
            schedule = schedule.copy()
            schedule['id'] = schedule_id
            schedule_list.append(schedule)

        return jsonify(schedule_list)

    @api.validate(base_schedule_schema, description='Schedule Object')
    @api.response(201, model=api_schedule_schema)
    @api.response(APIError)
    def post(self, session=None):
        """ Add new schedule """
        data = request.json

        if 'schedules' not in self.manager.config or not self.manager.config['schedules']:
            # Schedules not defined or are disabled, enable as one is being created
            self.manager.config['schedules'] = []

        self.manager.config['schedules'].append(data)
        schedules = self.manager.config['schedules']
        new_schedule, _ = _schedule_by_id(id(data), schedules)

        if not new_schedule:
            raise APIError('schedule went missing after add')

        self.manager.save_config()
        self.manager.config_changed()
        resp = jsonify(new_schedule)
        resp.status_code = 201
        return resp


@schedule_api.route('/<int:schedule_id>/')
@api.doc(params={'schedule_id': 'ID of Schedule'})
@api.doc(description=schedule_desc)
@api.response(NotFoundError)
class ScheduleAPI(APIResource):
    @etag
    @api.response(200, model=api_schedule_schema)
    def get(self, schedule_id, session=None):
        """ Get schedule details """
        schedules = self.manager.config.get('schedules', [])
        schedule, _ = _schedule_by_id(schedule_id, schedules)
        if schedule is None:
            raise NotFoundError('schedule %d not found' % schedule_id)

        job_id = scheduler_job_map.get(schedule_id)
        if job_id:
            job = scheduler.get_job(job_id)
            if job:
                schedule['next_run_time'] = job.next_run_time
        return jsonify(schedule)

    def _update_schedule(self, existing, update, merge=False):
        if 'id' in update:
            del update['id']

        if not merge:
            existing.clear()

        existing.update(update)
        self.manager.save_config()
        self.manager.config_changed()
        return existing

    @api.validate(base_schedule_schema, description='Updated Schedule Object')
    @api.response(201, model=api_schedule_schema)
    def put(self, schedule_id, session=None):
        """ Update schedule """
        new_schedule = request.json

        schedules = self.manager.config.get('schedules', [])
        schedule, idx = _schedule_by_id(schedule_id, schedules)
        if not schedule:
            raise NotFoundError('schedule %d not found' % schedule_id)

        new_schedule['id'] = id(schedule)
        self.manager.config['schedules'][idx] = new_schedule

        self.manager.save_config()
        self.manager.config_changed()
        resp = jsonify(new_schedule)
        resp.status_code = 201
        return resp

    @api.response(200, description='Schedule deleted', model=base_message_schema)
    def delete(self, schedule_id, session=None):
        """ Delete a schedule """
        for i in range(len(self.manager.config.get('schedules', []))):
            if id(self.manager.config['schedules'][i]) == schedule_id:
                del self.manager.config['schedules'][i]
                self.manager.save_config()
                self.manager.config_changed()
                return success_response('schedule %d successfully deleted' % schedule_id)

        raise NotFoundError('schedule %d not found' % schedule_id)
