from __future__ import unicode_literals, division, absolute_import
import logging
from math import ceil
from datetime import datetime

from flask import jsonify

from sqlalchemy import Column, String, Integer, DateTime, Unicode, desc

from flexget import options, plugin
from flexget.api import api, APIResource
from flexget.event import event
from flexget.logger import console
from flexget.manager import Base, Session

log = logging.getLogger('history')


class History(Base):

    __tablename__ = 'history'

    id = Column(Integer, primary_key=True)
    task = Column('feed', String)
    filename = Column(String)
    url = Column(String)
    title = Column(Unicode)
    time = Column(DateTime)
    details = Column(String)

    def __init__(self):
        self.time = datetime.now()

    def __str__(self):
        return '<History(filename=%s,task=%s)>' % (self.filename, self.task)

    def to_dict(self):
        return {
            'id': self.id,
            'task': self.task,
            'filename': self.filename,
            'url': self.url,
            'title': self.title,
            'time': self.time.isoformat(),
            'details': self.details,
        }


class PluginHistory(object):
    """Records all accepted entries for later lookup"""

    schema = {'type': 'boolean'}

    def on_task_learn(self, task, config):
        """Add accepted entries to history"""
        if config is False:
            return  # Explicitly disabled with configuration

        for entry in task.accepted:
            item = History()
            item.task = task.name
            item.filename = entry.get('output', None)
            item.title = entry['title']
            item.url = entry['url']
            reason = ''
            if 'reason' in entry:
                reason = ' (reason: %s)' % entry['reason']
            item.details = 'Accepted by %s%s' % (entry.get('accepted_by', '<unknown>'), reason)
            task.session.add(item)


def do_cli(manager, options):
    session = Session()
    try:
        console('-- History: ' + '-' * 67)
        query = session.query(History)
        if options.search:
            search_term = options.search.replace(' ', '%').replace('.', '%')
            query = query.filter(History.title.like('%' + search_term + '%'))
        if options.task:
            query = query.filter(History.task.like('%' + options.task + '%'))
        query = query.order_by(desc(History.time)).limit(options.limit)
        for item in reversed(query.all()):
            console(' Task    : %s' % item.task)
            console(' Title   : %s' % item.title)
            console(' Url     : %s' % item.url)
            if item.filename:
                console(' Stored  : %s' % item.filename)
            console(' Time    : %s' % item.time.strftime("%c"))
            console(' Details : %s' % item.details)
            console('-' * 79)
    finally:
        session.close()


@event('options.register')
def register_parser_arguments():
    parser = options.register_command('history', do_cli, help='view the history of entries that FlexGet has accepted')
    parser.add_argument('--limit', action='store', type=int, metavar='NUM', default=50,
                        help='limit to %(metavar)s results')
    parser.add_argument('--search', action='store', metavar='TERM', help='limit to results that contain %(metavar)s')
    parser.add_argument('--task', action='store', metavar='TASK', help='limit to results in specified %(metavar)s')


@event('plugin.register')
def register_plugin():
    plugin.register(PluginHistory, 'history', builtin=True, api_ver=2)


history_api = api.namespace('history', description='Entry History')

history_api_schema = {
    'type': 'object',
    'properties': {
        'items': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'details': {'type': 'string'},
                    'filename': {'type': 'string'},
                    'id': {'type': 'integer'},
                    'task': {'type': 'string'},
                    'time': {'type': 'string'},
                    'title': {'type': 'string'},
                    'url': {'type': 'string'}
                }
            }
        },
        'pages': {'type': 'integer'}
    }
}

history_api_schema = api.schema('history', history_api_schema)

history_parser = api.parser()
history_parser.add_argument('page', type=int, required=False, default=1, help='Page number')
history_parser.add_argument('max', type=int, required=False, default=50, help='Results per page')
history_parser.add_argument('task', type=str, required=False, default=None, help='Filter by task name')


@history_api.route('/')
@api.doc(parser=history_parser)
class HistoryAPI(APIResource):

    @api.response(404, 'page does not exist')
    @api.response(200, 'history results', history_api_schema)
    def get(self, session=None):
        """ List entries """
        args = history_parser.parse_args()
        page = args['page']
        max_results = args['max']
        task = args['task']

        if task:
            count = session.query(History).filter(History.task == task).count()
        else:
            count = session.query(History).count()

        if not count:
            return {'items': [], 'pages': 0}

        pages = int(ceil(count / float(max_results)))

        if page > pages:
            return {'error': 'page %s does not exist' % page}, 404

        start = (page - 1) * max_results
        finish = start + max_results

        if task:
            items = session.query(History).filter(History.task == task).order_by(desc(History.time)).slice(start, finish)
        else:
            items = session.query(History).order_by(desc(History.time)).slice(start, finish)

        return jsonify({
            'items': [item.to_dict() for item in items],
            'pages': pages
        })
