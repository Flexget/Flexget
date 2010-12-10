"""
At the moment scheduler supports just one global interval for all feeds.
"""

import logging
from datetime import datetime, timedelta
import threading
from sqlalchemy import Column, Integer, Unicode, asc, desc
from flask import request, render_template, flash, Module
from flexget.webui import register_plugin, db_session, manager
from flexget.manager import Base
from flexget.event import event, fire_event

from log_viewer import LogEntry

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


class RepeatingTimer(threading.Thread):
    """Call a function every certain number of seconds"""

    def __init__(self, interval, function, args=[], kwargs={}):
        threading.Thread.__init__(self)
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.finished = threading.Event()
        self.waiting = threading.Event()
        self.forced = threading.Event()

    def change_interval(self, interval):
        """Change the interval for the repeating"""
        self.interval = interval
        self.waiting.set()

    def exec_now(self):
        """Causes the timer to stop waiting and execute now"""
        self.forced.set()
        self.waiting.set()

    def cancel(self):
        """Stop the repeating"""
        self.finished.set()
        self.waiting.set()

    def run(self):
        last_run = datetime.now()
        while not self.finished.is_set():
            self.waiting.clear()
            self.forced.clear()
            wait_delta = (last_run + timedelta(seconds=self.interval) - datetime.now())
            wait_secs = (wait_delta.seconds + wait_delta.days * 24 * 3600)
            if wait_secs > 0:
                log.debug('Waiting %s to execute.' % wait_secs)
                self.waiting.wait(wait_secs)
            else:
                log.debug('We were scheduled to execute %d seconds ago, executing now.' % - wait_secs)
            if self.waiting.is_set():
                if not self.forced.is_set():
                    # If waiting was cancelled but the forced flag is not true
                    continue
            if not self.finished.is_set():
                last_run = datetime.now()
                self.function(*self.args, **self.kwargs)


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


@schedule.context_processor
def update_menus():
    import time

    strftime = lambda secs: time.strftime('%Y-%m-%d %H:%M', time.localtime(float(secs)))
    menu_feeds = [i[0] for i in db_session.query(LogEntry.feed).filter(LogEntry.feed != '')
                                          .distinct().order_by(asc('feed'))[:]]
    menu_execs = [(i[0], strftime(i[0])) for i in db_session.query(LogEntry.execution)
                                                            .filter(LogEntry.execution != '')
                                                            .distinct().order_by(desc('execution'))[:10]]
    return {'menu_feeds': menu_feeds, 'menu_execs': menu_execs}


@schedule.route('/', methods=['POST', 'GET'])
def index():
    global timer
    if request.method == 'POST':
        if request.form.get('submit') == 'Run Now':
            log.info('Manual execution forced')
            flash('Manual execution has been started.', 'info')
            timer.exec_now()
        try:
            interval = float(request.form['interval'])
        except ValueError:
            flash('Interval must be a number!', 'error')
        else:
            if interval <= 0:
                flash('Interval must be greater than zero!', 'error')
            else:
                unit = request.form['unit']
                delta = timedelta(**{unit: interval})
                # Convert the timedelta to integer minutes
                interval = int((delta.seconds + delta.days * 24 * 3600) / 60.0 + 0.5)
                log.info('new interval: %s minutes' % interval)
                set_global_interval(interval)
                flash('Scheduling updated successfully.', 'success')
                timer.change_interval(interval * 60)

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
    manager.create_feeds()
    manager.execute()


@event('webui.start')
def start_timer():
    # autoreload will fail if there are pending timers
    if manager.options.autoreload:
        log.info('Aborting start_timer() because --autoreload is enabled')
        return

    interval = get_global_interval()
    global timer
    if timer is None:
        timer = RepeatingTimer(interval * 60, execute)
        log.debug('Starting scheduler (%s minutes)' % interval)
        timer.start()


@event('webui.stop')
def stop_timer():
    log.info('Terminating')
    global timer
    if timer:
        timer.cancel()


register_plugin(schedule, menu='Schedule')
