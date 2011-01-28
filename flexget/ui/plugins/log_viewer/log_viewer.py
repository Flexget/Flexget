import logging
from datetime import datetime
from flask import render_template, Module, jsonify, request
from sqlalchemy import Column, DateTime, Integer, Unicode, Numeric, String, asc, desc, or_, and_
from flexget.ui.webui import register_plugin, db_session
from flexget.manager import Base, Session
from flexget.event import event

log_viewer = Module(__name__)


class LogEntry(Base):
    __tablename__ = 'log'

    id = Column(Integer, primary_key=True)
    created = Column(DateTime)
    logger = Column(String)
    levelno = Column(Integer)
    message = Column(Unicode)
    feed = Column(Unicode)
    execution = Column(String)

    def __init__(self, record):
        self.created = datetime.fromtimestamp(record.created)
        self.logger = record.name
        self.levelno = record.levelno
        self.message = record.getMessage()
        self.feed = getattr(record, 'feed', '')
        self.execution = getattr(record, 'execution', '')


class DBLogHandler(logging.Handler):
    
    def emit(self, record):
        session = Session()
        session.add(LogEntry(record))
        session.commit()
        session.close()


@log_viewer.context_processor
def update_menus():
    import time

    strftime = lambda secs: time.strftime('%Y-%m-%d %H:%M', time.localtime(float(secs)))
    menu_feeds = [i[0] for i in db_session.query(LogEntry.feed).filter(LogEntry.feed != '')
                                          .distinct().order_by(asc('feed'))[:]]
    menu_execs = [(i[0], strftime(i[0])) for i in db_session.query(LogEntry.execution)
                                                            .filter(LogEntry.execution != '')
                                                            .distinct().order_by(desc('execution'))[:10]]
    return {'menu_feeds': menu_feeds, 'menu_execs': menu_execs}


@log_viewer.route('/')
def index():
    return render_template('log_viewer/log.html')


@log_viewer.route('/_get_logdata.json')
def get_logdata():
    log_type = request.args.get('log_type')
    feed = request.args.get('feed')
    execution = request.args.get('exec')
    page = int(request.args.get('page'))
    limit = int(request.args.get('rows', 0))
    sidx = request.args.get('sidx')
    sord = request.args.get('sord')
    sord = desc if sord == 'desc' else asc
    # Generate the filtered query
    query = db_session.query(LogEntry)
    if log_type == 'webui':
        query = query.filter(or_(LogEntry.logger.in_(['webui', 'werkzeug', 'event']), LogEntry.logger.like('ui%')))
    elif log_type == 'core':
        query = query.filter(and_(~LogEntry.logger.in_(['webui', 'werkzeug', 'event']), ~LogEntry.logger.like('ui%')))
    if feed:
        query = query.filter(LogEntry.feed == feed)
    if execution:
        query = query.filter(LogEntry.execution == execution)
    count = query.count()
    # Use a trick to do ceiling division
    total_pages = 0 - ((0 - count) / limit)
    if page > total_pages:
        page = total_pages
    start = limit * page - limit
    json = {'total': total_pages,
            'page': page,
            'records': count,
            'rows': []}
    result = query.order_by(sord(sidx))[start:start + limit]
    for entry in result:
        json['rows'].append({'id': entry.id,
                             'created': entry.created.strftime('%Y-%m-%d %H:%M'),
                             'levelno': logging.getLevelName(entry.levelno),
                             'logger': entry.logger,
                             'feed': entry.feed,
                             'message': entry.message})
    return jsonify(json)


@event('webui.start')
def initialize():
    # Register db handler with base logger
    logger = logging.getLogger()
    handler = DBLogHandler()
    logger.addHandler(handler)

register_plugin(log_viewer, url_prefix='/log', menu='Log', order=256)
