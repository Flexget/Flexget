import logging
from flexget.webui import register_plugin, manager
from flexget.manager import Base, Session
from flask import render_template, Module, jsonify, request
from sqlalchemy import Column, DateTime, Integer, Unicode, String
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


@log_viewer.route('/_get_updates')
def get_updates():
    last_time = datetime.fromtimestamp(float(request.args.get('last_time', 0)))
    results = Session().query(LogEntry).filter(LogEntry.created > last_time)
    items = []
    for entry in results:
        args = {'asctime': entry.created.strftime('%Y-%m-%d %H:%M'),
                'levelname': logging.getLevelName(entry.levelno),
                'logger': entry.logger,
                'message': entry.message}
        items.append('%(asctime)-15s %(levelname)-6s %(logger)-10s %(message)s' % args)
    return jsonify(items=items, time=time.mktime(datetime.now().timetuple()))


def on_load():
    Base.metadata.create_all(bind=manager.engine)
    # Register db handler with base logger
    logger = logging.getLogger()
    handler = DBLogHandler(Session())
    logger.addHandler(handler)


on_load()
register_plugin(log_viewer, url_prefix='/log', menu='Log', order=256)
