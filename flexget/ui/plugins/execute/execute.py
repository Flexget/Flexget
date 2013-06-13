from __future__ import unicode_literals, division, absolute_import
import logging
from Queue import Empty
from flask import render_template, request, flash
from flask import Module, escape, jsonify
from flexget.ui.webui import register_plugin, manager, executor
from flexget.ui.executor import BufferQueue

execute = Module(__name__, url_prefix='/execute')

log = logging.getLogger('ui.execute')

bufferqueue = BufferQueue()


@execute.route('/', methods=['POST', 'GET'])
def index():
    context = {'progress': manager.parser.get_help().split('\n')}
    if request.method == 'POST':
        parser = manager.parser.parse_args(request.form.get('options', ''))
        if manager.parser.error_msg:
            flash(escape(manager.parser.error_msg), 'error')
            context['options'] = request.form['options']
        else:
            executor.execute(parsed_options=parser, output=bufferqueue)
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
