"""
At the moment scheduler supports just one global interval for all feeds.
"""

import logging
from flexget.webui import register_plugin, db_session
from flask import request, render_template, flash, Module
from flexget.manager import Base
from sqlalchemy import Column, Integer, Unicode
from threading import Timer

log = logging.getLogger('ui.schedule')
schedule = Module(__name__)


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
    # return 60


@schedule.route('/', methods=['POST', 'GET'])
def index():
    if request.method == 'POST':
        interval = int(request.form['interval'])
        log.info('new interval: %s' % interval)
        set_global_interval(interval)
        flash('Updated interval')
        
    context = {}
    global_interval = get_global_interval()
    if global_interval:
        context['interval'] = global_interval
    else:
        flash('Interval not set')
        context['interval'] = ''
    return render_template('schedule.html', **context)


register_plugin(schedule, menu='Schedule')
