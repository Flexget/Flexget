"""
At the moment scheduler supports just one global interval for all feeds.
"""
from copy import copy
import logging
from datetime import datetime, timedelta
import threading
from sqlalchemy import Column, Integer, Unicode
from flask import request, render_template, flash, Module, redirect, url_for
from flexget.ui.webui import register_plugin, db_session, manager, executor
from flexget.manager import Base
from flexget.event import event, fire_event

log = logging.getLogger('ui.schedule')
schedule = Module(__name__)

DEFAULT_INTERVAL = 60

timers = {}


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
        self.daemon = True
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.finished = threading.Event()
        self.waiting = threading.Event()

    def change_interval(self, interval):
        """Change the interval for the repeating"""
        self.interval = interval
        self.waiting.set()

    def cancel(self):
        """Stop the repeating"""
        self.finished.set()
        self.waiting.set()

    def run(self):
        last_run = datetime.now()
        while not self.finished.is_set():
            self.waiting.clear()
            wait_delta = (last_run + timedelta(seconds=self.interval) - datetime.now())
            wait_secs = (wait_delta.seconds + wait_delta.days * 24 * 3600)
            if wait_secs > 0:
                log.debug('Waiting %s to execute.' % wait_secs)
                self.waiting.wait(wait_secs)
            else:
                log.debug('We were scheduled to execute %d seconds ago, executing now.' % - wait_secs)
            if self.waiting.is_set():
                # If waiting was cancelled do not execute the function
                continue
            if not self.finished.is_set():
                last_run = datetime.now()
                self.function(*self.args, **self.kwargs)


def get_feed_interval(feed):
    feed_interval = db_session.query(Schedule).filter(Schedule.feed == feed).first()
    if feed_interval:
        return feed_interval.interval


def set_feed_interval(feed, interval):
    feed_interval = db_session.query(Schedule).filter(Schedule.feed == feed).first()
    if feed_interval:
        log.debug('Updating %s interval' % feed)
        feed_interval.interval = interval
    else:
        log.debug('Creating new %s interval' % feed)
        db_session.add(Schedule(feed, interval))
    db_session.commit()


@schedule.context_processor
def get_intervals():
    schedule_items = db_session.query(Schedule).filter(Schedule.feed != '__DEFAULT__').all()
    default_interval = db_session.query(Schedule).filter(Schedule.feed == '__DEFAULT__').first()
    if default_interval:
        default_interval = default_interval.interval
    else:
        default_interval = DEFAULT_INTERVAL
    return {'default_interval': default_interval,
            'schedule_items': schedule_items,
            'feeds': set(get_all_feeds()) - set(get_scheduled_feeds())}


def update_interval(form, feed):
    try:
        interval = float(form[feed + '_interval'])
    except ValueError:
        flash('%s interval must be a number!' % feed.capitalize(), 'error')
    else:
        if interval <= 0:
            flash('%s nterval must be greater than zero!' % feed.capitalize(), 'error')
        else:
            unit = form[feed + '_unit']
            delta = timedelta(**{unit: interval})
            # Convert the timedelta to integer minutes
            interval = int((delta.seconds + delta.days * 24 * 3600) / 60.0)
            if interval <= 0:
                interval = 1
            log.info('new interval for %s: %d minutes' % (feed, interval))
            set_feed_interval(feed, interval)
            start_timer(feed, interval)
            flash('%s scheduling updated successfully.' % feed.capitalize(), 'success')


@schedule.route('/', methods=['POST', 'GET'])
def index():
    # TODO: Only allow global interval if --feed plugin isn't available
    global timer
    if request.method == 'POST':
        for feed in get_all_feeds() + [u'__DEFAULT__']:
            if request.form.get(feed + '_interval'):
                update_interval(request.form, feed)

    return render_template('schedule/schedule.html')


@schedule.route('/delete/<feed>')
def delete_schedule(feed):
    stop_timer(feed)
    db_session.query(Schedule).filter(Schedule.feed == feed).delete()
    db_session.commit()
    return redirect(url_for('index'))


@schedule.route('/add/<feed>')
def add_schedule(feed):
    schedule = db_session.query(Schedule).filter(Schedule.feed == feed).first()
    if not schedule:
        schedule = Schedule(feed, DEFAULT_INTERVAL)
    db_session.merge(schedule)
    db_session.commit()
    start_timer(feed, DEFAULT_INTERVAL)
    return redirect(url_for('index'))


def get_all_feeds():
    return [feed for feed in manager.config.get('feeds', {}).keys() if not feed.startswith('_')]


def get_scheduled_feeds():
    return [item.feed for item in db_session.query(Schedule).all()]


def execute(feed):
    """Adds a run to the executor"""
    # Get a copy of the options from the manager
    run_opts = copy(manager.options)
    if feed == u'__GLOBAL__':
        # Get a list of all feeds that do not have their own schedule
        feeds = set(get_all_feeds()) - set(get_scheduled_feeds())
        # Use the --feed plugin to run only desired feeds
        run_opts.onlyfeed = ','.join(feeds)
        log.info('Executing feeds: %s' % ", ".join(feeds))
    else:
        # Only run the passed feed
        run_opts.onlyfeed = feed
        log.info('Executing feed: %s' % feed)
    fire_event('scheduler.execute')
    executor.execute(options=run_opts)


def start_timer(feed, interval):
    # autoreload will fail if there are pending timers
    if manager.options.autoreload:
        log.info('Aborting start_timer() because --autoreload is enabled')
        return

    log.debug('Starting %s scheduler (%s minutes)' % (feed, interval))
    global timers
    if not timers.get(feed):
        timers[feed] = RepeatingTimer(interval * 60, execute, (feed,))
        timers[feed].start()
    else:
        timers[feed].change_interval(interval * 60)


def stop_timer(feed):
    global timers
    if timers.get(feed):
        timers[feed].cancel()
        del timers[feed]


@event('webui.start')
def on_webui_start():
    # Start timers for all schedules
    for item in db_session.query(Schedule):
        start_timer(item.feed, item.interval)


@event('webui.stop')
def on_webui_stop():
    log.info('Terminating')
    # Stop all running timers
    for feed in [f for f in timers]:
        stop_timer(feed)


register_plugin(schedule, menu='Schedule')
