from __future__ import unicode_literals, division, absolute_import
import logging
from Queue import Empty

from flask import render_template, request, flash
from flask import Blueprint, escape, jsonify

from flexget.options import CoreArgumentParser, RaiseErrorArgumentParser
from flexget.ui.webui import register_plugin
from flexget.scheduler import BufferQueue

execute = Blueprint('execute', __name__)

log = logging.getLogger('ui.execute')

bufferqueue = BufferQueue()
exec_parser = RaiseErrorArgumentParser(parents=[CoreArgumentParser().get_subparser('execute')])

@execute.route('/', methods=['POST', 'GET'])
def index():
    context = {'progress': exec_parser.format_help().split('\n')}
    if request.method == 'POST':
        try:
            options = exec_parser.parse_args(request.form.get('options', ''))
        except ValueError as e:
            flash(escape(e.message), 'error')
            context['options'] = request.form['options']
        else:
            executor.execute(options=options, output=bufferqueue)
            context['execute_progress'] = True
            context['progress'] = progress(as_list=True)

    return render_template('execute/execute.html', **context)


@execute.route('/progress.json')
def progress(as_list=False):
    """
    Gets messages from the queue and exports them to JSON.
    """
    result = {'items': []}
    try:
        while True:
            item = bufferqueue.get_nowait()
            result['items'].append(item)
            bufferqueue.task_done()
    except Empty:
        pass

    if as_list:
        return result['items']

    return jsonify(result)


register_plugin(execute, menu='Execute')
