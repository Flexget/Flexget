"""
At the moment scheduler supports just one global interval for all feeds.
"""

import logging
from flexget.webui import register_plugin, db_session, manager
from flask import request, render_template, flash, Module
from flexget.manager import Base
from sqlalchemy import Column, Integer, Unicode
from threading import Timer
from flexget.event import event, fire_event

log = logging.getLogger('ui.schedule')
schedule = Module(__name__)

DEFAULT_INTERVAL = 60

timer = None


class Schedule(Base):
    __tablename__ = 'schedule'

    id = Column(Integer, primary_key=True)
    feed = Column(Unicode)
    interval = Column(Integer)

    def __init__(self, feed, interval):
        self.feed = feed
        self.interval = interval


def set_global_interval(interval):
    global_interval = db_session.query(Schedule).filter(Schedule.feed == u'__GLOBAL__').first()
    if global_interval:
        log.debug('Updating global interval')
        global_interval.interval = interval
    else:
        log.debug('Creating new global interval')
        db_session.add(Schedule(u'__GLOBAL__', interval))
    db_session.commit()


def get_global_interval():
    global_interval = db_session.query(Schedule).filter(Schedule.feed == u'__GLOBAL__').first()
    if global_interval:
        return global_interval.interval
    return DEFAULT_INTERVAL


@schedule.route('/', methods=['POST', 'GET'])
def index():
    if request.method == 'POST':
        interval = int(request.form['interval'])
        if interval == 0:
            flash('Interval cannot be zero!')
        else:
            log.info('new interval: %s' % interval)
            set_global_interval(interval)
            flash('Scheduling updated successfully')
            # cancel old timer and create new one
            if timer is not None:
                timer.cancel()
            start_timer()

    context = {}
    global_interval = get_global_interval()
    if global_interval:
        context['interval'] = global_interval
    else:
        flash('Interval not set')
        context['interval'] = ''
    return render_template('schedule.html', **context)


def execute():
    log.info('Executing feeds')
    fire_event('scheduler.execute')
    manager.execute()
    # restart timer
    start_timer()


@event('webui.start')
def start_timer():
    # autoreload will fail if there are pending timers
    if manager.options.autoreload:
        log.info('Aborting start_timer() because --autoreload is enabled')
        return

    interval = get_global_interval()
    global timer
    timer = Timer(interval * 60, execute)
    log.debug('Starting scheduler (%s minutes)' % interval)
    timer.start()


register_plugin(schedule, menu='Schedule')
