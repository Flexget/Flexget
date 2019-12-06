import copy

from flask import jsonify, request

from flexget.api import APIResource, api
from flexget.api.app import (
    APIError,
    Conflict,
    NotFoundError,
    base_message_schema,
    etag,
    success_response,
)
from flexget.components.scheduler.scheduler import (
    DEFAULT_SCHEDULES,
    schedule_schema,
    scheduler,
    scheduler_job_map,
)

schedule_api = api.namespace('schedules', description='Task Scheduler')


class ObjectsContainer:
    # SwaggerUI does not yet support anyOf or oneOf
    schedule_object = copy.deepcopy(schedule_schema)
    schedule_object['properties']['id'] = {'type': 'integer'}
    schedule_object['maxProperties'] += 1

    schedules_list = {'type': 'array', 'items': schedule_object}


base_schedule_schema = api.schema_model('schedules.base', schedule_schema)
api_schedule_schema = api.schema_model('schedules.schedule', ObjectsContainer.schedule_object)
api_schedules_list_schema = api.schema_model('schedules.list', ObjectsContainer.schedules_list)


def _schedule_by_id(schedule_id, schedules):
    for idx, schedule in enumerate(schedules):
        if schedule and id(schedule) == schedule_id:
            schedule = schedule.copy()
            schedule['id'] = schedule_id
            return schedule, idx
    return None, None


schedule_desc = (
    "Schedule ID changes upon daemon restart. The schedules object supports either interval or schedule"
    " (cron) objects, see the model definition for details. Tasks also support string or list "
    "(Not displayed as Swagger does yet not support anyOf or oneOf."
)


@schedule_api.route('/')
@api.doc(description=schedule_desc)
@api.response(Conflict)
class SchedulesAPI(APIResource):
    @etag
    @api.response(200, model=api_schedules_list_schema)
    def get(self, session=None):
        """ List schedules """
        schedule_list = []

        schedules = self.manager.config.get('schedules', [])

        # Checks for boolean config
        if schedules is True:
            schedules = DEFAULT_SCHEDULES
        elif schedules is False:
            raise Conflict('Schedules are disables in config')

        for schedule in schedules:
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

        schedules = self.manager.config.get('schedules', [])

        # Checks for boolean config
        if schedules is True:
            schedules = DEFAULT_SCHEDULES
        elif schedules is False:
            raise Conflict('Schedules are disables in config')

        self.manager.config['schedules'] = schedules

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


# noinspection PyUnusedLocal
@schedule_api.route('/<int:schedule_id>/')
@api.doc(params={'schedule_id': 'ID of Schedule'})
@api.doc(description=schedule_desc)
@api.response(NotFoundError)
@api.response(Conflict)
class ScheduleAPI(APIResource):
    @etag
    @api.response(200, model=api_schedule_schema)
    def get(self, schedule_id, session=None):
        """ Get schedule details """
        schedules = self.manager.config.get('schedules', [])

        # Checks for boolean config
        if schedules is True:
            schedules = DEFAULT_SCHEDULES
        elif schedules is False:
            raise Conflict('Schedules are disables in config')

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

        # Checks for boolean config
        if schedules is True:
            self.manager.config['schedules'] = DEFAULT_SCHEDULES
        elif schedules is False:
            raise Conflict('Schedules are disables in config')

        schedule, idx = _schedule_by_id(schedule_id, self.manager.config['schedules'])
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
        schedules = self.manager.config.get('schedules')

        # Checks for boolean config
        if schedules is True:
            raise Conflict('Schedules usage is set to default, cannot delete')
        elif schedules is False:
            raise Conflict('Schedules are disables in config')

        for i in range(len(self.manager.config.get('schedules', []))):
            if id(self.manager.config['schedules'][i]) == schedule_id:
                del self.manager.config['schedules'][i]
                self.manager.save_config()
                self.manager.config_changed()
                return success_response('schedule %d successfully deleted' % schedule_id)

        raise NotFoundError('schedule %d not found' % schedule_id)
