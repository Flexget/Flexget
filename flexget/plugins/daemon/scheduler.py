from __future__ import unicode_literals, division, absolute_import
import hashlib
import logging

import pytz
import tzlocal
import struct
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from flask import request, jsonify

from flexget.config_schema import register_config_key, format_checker, register_schema
from flexget.event import event
from flexget.manager import Base, manager
from flexget.utils import json
from flexget.api import api, APIResource

log = logging.getLogger('scheduler')


# Add a format checker for more detailed errors on cron type schedules
@format_checker.checks('cron_schedule', raises=ValueError)
def is_cron_schedule(instance):
    if not isinstance(instance, dict):
        return True
    try:
        return CronTrigger(**instance)
    except TypeError:
        # A more specific error message about which key will also be shown by properties schema keyword
        raise ValueError('Invalid key for schedule.')


UNITS = ['minutes', 'hours', 'days', 'weeks']
interval_schema = {
    'type': 'object',
    'title': 'Simple Interval',
    'properties': {
        'minutes': {'type': 'number'},
        'hours': {'type': 'number'},
        'days': {'type': 'number'},
        'weeks': {'type': 'number'}
    },
    # Only allow one unit to be specified
    'maxProperties': 1,
    'error_maxProperties': 'Interval must be specified as one of %s' % ', '.join(UNITS),
    'additionalProperties': False
}

cron_schema = {
    'type': 'object',
    'title': 'Advanced Cron Interval',
    'properties': {
        'year': {'type': ['integer', 'string']},
        'month': {'type': ['integer', 'string']},
        'day': {'type': ['integer', 'string']},
        'week': {'type': ['integer', 'string']},
        'day_of_week': {'type': ['integer', 'string']},
        'hour': {'type': ['integer', 'string']},
        'minute': {'type': ['integer', 'string']}
    },
    'additionalProperties': False
}

schedule_schema = {
    'type': 'object',
    'title': 'Schedule',
    'description': 'A schedule which runs specified tasks periodically.',
    'properties': {
        'tasks': {'type': ['array', 'string'], 'items': {'type': 'string'}},
        'interval': interval_schema,
        'schedule': cron_schema
    },
    'required': ['tasks'],
    'minProperties': 2,
    'maxProperties': 2,
    'error_minProperties': 'Either `cron` or `interval` must be defined.',
    'error_maxProperties': 'Either `cron` or `interval` must be defined.',
    'additionalProperties': False
}


main_schema = {
    'oneOf': [
        {
            'type': 'array',
            'title': 'Enable',
            'items': schedule_schema
        },
        {
            'type': 'boolean',
            'title': 'Disable',
            'description': 'Disable task schedules',
        }
    ]
}


scheduler = None
scheduler_job_map = {}


def job_id(conf):
    """Create a unique id for a schedule item in config."""
    return hashlib.sha1(json.dumps(conf, sort_keys=True)).hexdigest()


def run_job(tasks):
    """Add the execution to the queue and waits until it is finished"""
    from flexget.manager import manager
    finished_events = manager.execute(options={'tasks': tasks, 'cron': True}, priority=5)
    for task_id, task_name, event in finished_events:
        event.wait()


@event('manager.daemon.started')
def setup_scheduler(manager):
    """Configure and start apscheduler"""
    global scheduler
    if logging.getLogger().getEffectiveLevel() > logging.DEBUG:
        logging.getLogger('apscheduler').setLevel(logging.WARNING)
    jobstores = {'default': SQLAlchemyJobStore(engine=manager.engine, metadata=Base.metadata)}
    # If job was meant to run within last day while daemon was shutdown, run it once when continuing
    job_defaults = {'coalesce': True, 'misfire_grace_time': 60 * 60 * 24}
    try:
        timezone = tzlocal.get_localzone()
        if timezone.zone == 'local':
            timezone = None
    except pytz.UnknownTimeZoneError:
        timezone = None
    except struct.error as e:
        # Hiding exception that may occur in tzfile.py seen in entware
        log.warning('Hiding exception from tzlocal: %s', e)
        timezone = None
    if not timezone:
        # The default sqlalchemy jobstore does not work when there isn't a name for the local timezone.
        # Just fall back to utc in this case
        # FlexGet #2741, upstream ticket https://bitbucket.org/agronholm/apscheduler/issue/59
        log.info('Local timezone name could not be determined. Scheduler will display times in UTC for any log'
                 'messages. To resolve this set up /etc/timezone with correct time zone name.')
        timezone = pytz.utc
    scheduler = BackgroundScheduler(jobstores=jobstores, job_defaults=job_defaults, timezone=timezone)
    setup_jobs(manager)


@event('manager.config_updated')
def setup_jobs(manager):
    """Set up the jobs for apscheduler to run."""
    if not manager.is_daemon:
        return

    global scheduler_job_map
    scheduler_job_map = {}

    if 'schedules' not in manager.config:
        log.info('No schedules defined in config. Defaulting to run all tasks on a 1 hour interval.')
    config = manager.config.get('schedules', True)
    if config is True:
        config = [{'tasks': ['*'], 'interval': {'hours': 1}}]
    elif not config:  # Schedules are disabled with `schedules: no`
        if scheduler.running:
            log.info('Shutting down scheduler')
            scheduler.shutdown()
        return
    existing_job_ids = [job.id for job in scheduler.get_jobs()]
    configured_job_ids = []
    for job_config in config:
        jid = job_id(job_config)
        configured_job_ids.append(jid)
        scheduler_job_map[id(job_config)] = jid
        if jid in existing_job_ids:
            continue
        if 'interval' in job_config:
            trigger, trigger_args = 'interval', job_config['interval']
        else:
            trigger, trigger_args = 'cron', job_config['schedule']
        tasks = job_config['tasks']
        if not isinstance(tasks, list):
            tasks = [tasks]
        name = ','.join(tasks)
        scheduler.add_job(run_job, args=(tasks,), id=jid, name=name, trigger=trigger, **trigger_args)
    # Remove jobs no longer in config
    for jid in existing_job_ids:
        if jid not in configured_job_ids:
            scheduler.remove_job(jid)
    if not scheduler.running:
        log.info('Starting scheduler')
        scheduler.start()


@event('manager.shutdown_requested')
def shutdown_requested(manager):
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=True)


@event('manager.shutdown')
def stop_scheduler(manager):
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)


@event('config.register')
def register_config():
    register_config_key('schedules', main_schema)
    register_schema('/schema/config/schedule', schedule_schema)


schedule_api = api.namespace('schedules', description='Task Scheduler')

api_schedule_schema = api.schema('schedule', schedule_schema)
api_schedules_list_schema = api.schema('schedule', main_schema)

def _schedule_by_id(schedule_id):
    for schedule in manager.config.get('schedules', []):
        if id(schedule) == schedule_id:
            schedule = schedule.copy()
            schedule['id'] = schedule_id
            return schedule


@schedule_api.route('/')
class SchedulesAPI(APIResource):

    @api.response(200, 'List of schedules', api_schedules_list_schema)
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

    @api.validate(api_schedule_schema)
    @api.response(201, 'Newly created schedule', api_schedule_schema)
    def post(self, session=None):
        """ Add new schedule """
        data = request.json

        if 'schedules' not in manager.config or not manager.config['schedules']:
            # Schedules not defined or are disabled, enable as one is being created
            manager.config['schedules'] = []

        manager.config['schedules'].append(data['schedule'])
        new_schedule = _schedule_by_id(id(data['schedule']))

        if not new_schedule:
            return {'error': 'schedule went missing after add'}, 500

        manager.save_config()
        manager.config_changed()
        return {'schedule': new_schedule}, 201


@schedule_api.route('/<int:schedule_id>/')
@api.doc(params={'schedule_id': 'ID of Schedule'})
@api.doc(description='Schedule ID changes upon daemon restart')
class ScheduleAPI(APIResource):

    # TODO: Add additional addtirbutes to schema (last, next run and id)
    @api.response(200, 'Schedule config', api_schedule_schema)
    @api.response(404, 'Schedule not found')
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

    @api.validate(api_schedule_schema)
    @api.response(200, 'Updated schedule', api_schedule_schema)
    @api.response(404, 'Schedule not found')
    def post(self, schedule_id, session=None):
        """ Update schedule """
        data = request.json
        schedule = self._get_schedule(schedule_id)

        if not schedule:
            return {'detail': 'invalid schedule id'}, 404

        new_schedule = self._update_schedule(schedule, data)
        return jsonify({'schedule': new_schedule})

    @api.response(404, 'Schedule not found')
    @api.response(200, 'Schedule deleted')
    def delete(self, schedule_id, session=None):
        """ Delete a schedule """
        for i in range(len(manager.config.get('schedules', []))):
            if id(manager.config['schedules'][i]) == schedule_id:
                del manager.config['schedules'][i]
                manager.save_config()
                manager.config_changed()
                return {}, 200

        return {'error': 'Schedule not found'}, 404
