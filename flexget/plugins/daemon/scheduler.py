from __future__ import unicode_literals, division, absolute_import
import hashlib
import logging

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from flexget.config_schema import register_config_key, format_checker
from flexget.event import event
from flexget.manager import Base
from flexget.utils import json

log = logging.getLogger('scheduler')


# Add a format checker for more detailed errors on cron type schedules
@format_checker.checks('cron_schedule', raises=ValueError)
def is_cron_schedule(instance):
    if not isinstance(instance, dict):
        return True
    return CronTrigger(**instance)


UNITS = ['minutes', 'hours', 'days', 'weeks']
interval_schema = {
    'type': 'object',
    'properties': {
        'minutes': {'type': 'number'},
        'hours': {'type': 'number'},
        'days': {'type': 'number'},
        'weeks': {'type': 'number'}
    },
    # Only allow one unit to be specified
    'oneOf': [{'required': [unit]} for unit in UNITS],
    'error_oneOf': 'Interval must be specified as one of %s' % ', '.join(UNITS),
    'additionalProperties': False
}

cron_schema = {
    'type': 'object',
    'properties': {
        'year': {'type': ['integer', 'string']},
        'month': {'type': ['integer', 'string']},
        'day': {'type': ['integer', 'string']},
        'week': {'type': ['integer', 'string']},
        'day_of_week': {'type': ['integer', 'string']},
        'hour': {'type': ['integer', 'string']},
        'minute': {'type': ['integer', 'string']}
    },
    'format': 'cron_schedule',
    'additionalProperties': False
}

main_schema = {
    'oneOf': [
        {
            'type': 'array',
            'items': {
                'properties': {
                    'tasks': {'type': ['array', 'string'], 'items': {'type': 'string'}},
                    'interval': interval_schema,
                    'schedule': cron_schema
                },
                'required': ['tasks'],
                'oneOf': [{'required': ['schedule']}, {'required': ['interval']}],
                'error_oneOf': 'Either `cron` or `interval` must be defined.',
                'additionalProperties': False
            }
        },
        {'type': 'boolean', 'enum': [False]}
    ]
}


scheduler = None


def job_id(conf):
    """Create a unique id for a schedule item in config."""
    return hashlib.sha1(json.dumps(conf, sort_keys=True)).hexdigest()


def run_job(tasks):
    """Add the execution to the queue and waits until it is finished"""
    from flexget.manager import manager
    finished_events = manager.execute(options={'tasks': tasks, 'cron': True}, priority=5)
    for event in finished_events:
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
    scheduler = BackgroundScheduler(jobstores=jobstores, job_defaults=job_defaults)
    setup_jobs(manager)


@event('manager.config_updated')
def setup_jobs(manager):
    """Set up the jobs for apscheduler to run."""
    if not manager.is_daemon:
        return
    if 'schedules' not in manager.config:
        log.info('No schedules defined in config. Defaulting to run all tasks on a 1 hour interval.')
    config = manager.config.get('schedules', [{'tasks': ['*'], 'interval': {'hours': 1}}])
    if not config and scheduler.running:
        log.info('Shutting down scheduler')
        scheduler.shutdown()
        return
    existing_job_ids = [job.id for job in scheduler.get_jobs()]
    configured_job_ids = []
    for job_config in config:
        jid = job_id(job_config)
        configured_job_ids.append(jid)
        if jid in existing_job_ids:
            continue
        if 'interval' in job_config:
            trigger = IntervalTrigger(**job_config['interval'])
        else:
            trigger = CronTrigger(**job_config['schedule'])
        tasks = job_config['tasks']
        if not isinstance(tasks, list):
            tasks = [tasks]
        name = ','.join(tasks)
        scheduler.add_job(run_job, trigger=trigger, args=(tasks,), id=jid, name=name)
    # Remove jobs no longer in config
    for jid in existing_job_ids:
        if jid not in configured_job_ids:
            scheduler.remove_job(jid)
    if not scheduler.running:
        log.info('Starting scheduler')
        scheduler.start()


@event('manager.daemon.completed')
def stop_scheduler(manager):
    if scheduler.running:
        scheduler.shutdown()


@event('config.register')
def register_config():
    register_config_key('schedules', main_schema)
