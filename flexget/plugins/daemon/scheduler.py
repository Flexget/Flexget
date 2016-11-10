from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import hashlib
import logging

import pytz
import tzlocal
import struct
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from flexget.config_schema import register_config_key, format_checker, register_schema
from flexget.event import event
from flexget.manager import Base, manager
from flexget.utils import json

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


DEFAULT_SCHEDULES = [{'tasks': ['*'], 'interval': {'hours': 1}}]

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
    return hashlib.sha1(json.dumps(conf, sort_keys=True).encode('utf-8')).hexdigest()


def run_job(tasks):
    """Add the execution to the queue and waits until it is finished"""
    log.debug('executing tasks: %s', tasks)
    finished_events = manager.execute(options={'tasks': tasks, 'cron': True, 'allow_manual': False}, priority=5)
    for _, task_name, event_ in finished_events:
        log.debug('task finished executing: %s', task_name)
        event_.wait()
    log.debug('all tasks in schedule finished executing')


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
        # FlexGet #2741, upstream ticket https://github.com/agronholm/apscheduler/issues/59
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
        config = DEFAULT_SCHEDULES
    elif not config:  # Schedules are disabled with `schedules: no`
        if scheduler.running:
            log.info('Shutting down scheduler')
            scheduler.shutdown()
        return
    if not scheduler.running:
        log.info('Starting scheduler')
        scheduler.start(paused=True)
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
    scheduler.resume()


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
