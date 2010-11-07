import logging
from flexget.webui import register_plugin, manager, db_session
from flexget.manager import Base, Session
from flask import render_template, Module, jsonify, request
from sqlalchemy import Column, DateTime, Integer, Unicode, String, asc, desc
import time
from datetime import datetime

log_viewer = Module(__name__)


class LogEntry(Base):
    __tablename__ = 'log'

    id = Column(Integer, primary_key=True)
    created = Column(DateTime)
    logger = Column(String)
    levelno = Column(Integer)
    message = Column(String)

    def __init__(self, record):
        self.created = datetime.fromtimestamp(record.created) #datetime.now()
        self.logger = record.name
        self.levelno = record.levelno
        self.message = record.getMessage()


class DBLogHandler(logging.Handler):

    def __init__(self, session):
        logging.Handler.__init__(self)
        self.session = session

    def emit(self, record):
        logentry = LogEntry(record)
        self.session.add(logentry)
        self.session.commit()


@log_viewer.route('/')
def index():
    return render_template('log.html')


@log_viewer.route('/_get_logdata.json')
def get_logdata():
    page = int(request.args.get('page'))
    limit = int(request.args.get('rows'))
    sidx = request.args.get('sidx')
    sord = request.args.get('sord', 'asc')
    sord = asc if sord == 'asc' else desc
    count = db_session.query(LogEntry).count()
    # Use a trick to do ceiling division
    total_pages = 0 - ((0 - count) / limit)
    if page > total_pages:
        page = total_pages
    start = limit * page - limit
    json = {'total': total_pages,
            'page': page,
            'records': limit,
            'rows': []}
    result = db_session.query(LogEntry).order_by(sord(sidx))[start:start + limit]
    for entry in result:
        json['rows'].append({'id': entry.id,
                             'created': entry.created.strftime('%Y-%m-%d %H:%M'),
                             'level': logging.getLevelName(entry.levelno),
                             'logger': entry.logger,
                             'message': entry.message})
    return jsonify(json)


def on_load():
    Base.metadata.create_all(bind=manager.engine)
    # Register db handler with base logger
    logger = logging.getLogger()
    handler = DBLogHandler(Session())
    logger.addHandler(handler)


on_load()
register_plugin(log_viewer, url_prefix='/log', menu='Log', order=256)
